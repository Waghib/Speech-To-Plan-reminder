import os
import json
import torch
import logging
import whisper
import soundfile as sf
import numpy as np
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, File, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from tempfile import gettempdir
import uvicorn
import google.generativeai as genai
from datetime import datetime, timedelta
from dotenv import load_dotenv
from database import SessionLocal, Todo
from sqlalchemy.orm import Session
from sqlalchemy import or_
import base64
import shutil
import time
import asyncio
import aiofiles

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TEMP_DIR = os.path.join(gettempdir(), 'audio_transcription')
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
GEMINI_TEMP_DIR = os.path.join(gettempdir(), "speech_to_plan")
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg.exe")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(GEMINI_TEMP_DIR, exist_ok=True)

# Load Whisper model
logger.info(f"Loading Whisper model on {DEVICE}...")
model = whisper.load_model("base")
model.to(DEVICE)

# Configure Gemini
genai.configure(api_key=os.getenv("gemini_api_key"))
gemini_model = genai.GenerativeModel('gemini-pro')

SYSTEM_PROMPT = """You are an AI To-Do List Assistant. Your role is to help users manage their tasks by adding, viewing, updating, and deleting them.
You MUST ALWAYS respond in JSON format with the following structure:

For actions:
{
  "type": "action",
  "function": "createTodo" | "getAllTodos" | "searchTodo" | "deleteTodoById",
  "input": {  // The input for the function
    "title": string,  // Required for createTodo and searchTodo
    "due_date": string  // Optional ISO date for createTodo
  } | number | number[]  // ID or array of IDs for deleteTodoById
}

For responses to the user:
{
  "type": "output",
  "output": string  // Your message to the user
}

Available Functions:
- getAllTodos: Get all todos from the database
- createTodo: Create a todo with title and optional due_date
- searchTodo: Search todos by title (also used for deletion by name)
- deleteTodoById: Delete todo(s) by ID (supports single ID or array of IDs)

Example interactions:

# Adding a task
User: "Add buy groceries for tomorrow"
Assistant: {
  "type": "action",
  "function": "createTodo",
  "input": {
    "title": "Buy groceries",
    "due_date": "2025-02-10"
  }
}

# Viewing tasks
User: "Show my tasks"
Assistant: {
  "type": "action",
  "function": "getAllTodos",
  "input": null
}

# Deleting by name
User: "Delete the groceries task"
Assistant: {
  "type": "action",
  "function": "searchTodo",
  "input": {
    "title": "groceries"
  }
}

# Deleting by ID
User: "Delete task 5"
Assistant: {
  "type": "action",
  "function": "deleteTodoById",
  "input": 5
}

# General chat
User: "thank you"
Assistant: {
  "type": "output",
  "output": "You're welcome! Let me know if you need help with anything else."
}
"""

# Initialize chat
chat = gemini_model.start_chat(history=[
    {"role": "user", "parts": [SYSTEM_PROMPT]},
])

# Create FastAPI app
app = FastAPI(title="Audio Transcription API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

class AudioData(BaseModel):
    audio: str

class TranscriptionResponse(BaseModel):
    success: bool
    transcription: Optional[str] = None
    error: Optional[str] = None

class Message(BaseModel):
    text: str

def save_audio_file(audio_data: str) -> Optional[str]:
    """Save base64 audio data to a temporary file."""
    try:
        # Remove data URL prefix if present
        if 'base64,' in audio_data:
            audio_data = audio_data.split('base64,')[1]

        # Decode base64 data
        audio_bytes = base64.b64decode(audio_data)

        # Create temporary file
        temp_path = os.path.join(TEMP_DIR, f'temp_audio_{os.urandom(8).hex()}.mp3')
        
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        return temp_path
    except Exception as e:
        logger.error(f"Error saving audio file: {str(e)}")
        return None

def load_audio(file_path: str) -> Optional[np.ndarray]:
    """Load audio file and return numpy array."""
    try:
        # Convert audio to WAV format with required specifications
        output_path = file_path.rsplit('.', 1)[0] + '_converted.wav'
        
        # FFmpeg command to convert audio to the required format
        command = [
            FFMPEG_PATH,
            '-i', file_path,
            '-ar', '16000',  # Sample rate: 16kHz
            '-ac', '1',      # Mono channel
            '-c:a', 'pcm_f32le',  # 32-bit float
            '-f', 'wav',
            '-y',  # Overwrite output file if it exists
            output_path
        ]
        
        logger.debug(f"Running FFmpeg command: {' '.join(command)}")
        
        # Run ffmpeg command
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True  # Raise exception if command fails
        )
        
        logger.debug(f"FFmpeg output: {process.stderr.decode()}")
            
        # Read the converted WAV file using soundfile
        audio, sr = sf.read(output_path, dtype='float32')
        logger.debug(f"Loaded audio with sample rate: {sr}Hz")
            
        # Normalize audio if it's not already normalized
        max_abs = np.max(np.abs(audio))
        logger.debug(f"Original audio range: [{np.min(audio)}, {np.max(audio)}], max abs: {max_abs}")
        
        if max_abs > 1.0:
            audio = audio / max_abs
        elif max_abs < 1e-3:  # If the audio is too quiet
            logger.warning("Audio signal is very weak, amplifying...")
            audio = audio * (0.5 / max_abs)  # Amplify to 50% of full scale
            
        logger.info(f"Successfully loaded audio: shape={audio.shape}, dtype={audio.dtype}, range=[{np.min(audio)}, {np.max(audio)}]")
        
        # Check for silence or very low volume
        rms = np.sqrt(np.mean(np.square(audio)))
        logger.debug(f"Audio RMS value: {rms}")
        
        if rms < 1e-4:
            logger.warning("Audio appears to be silent or very quiet")
            return None
        
        # Clean up converted file
        try:
            os.remove(output_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {output_path}: {e}")
        
        return audio
        
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg error: {e.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"Error loading audio: {str(e)}")
        return None

def process_audio_in_chunks(audio: np.ndarray, chunk_duration: int = 30, overlap: int = 1) -> str:
    """Process long audio files in chunks."""
    sample_rate = 16000
    chunk_size = chunk_duration * sample_rate
    overlap_size = overlap * sample_rate
    
    # Calculate number of chunks
    total_samples = len(audio)
    num_chunks = (total_samples - overlap_size) // (chunk_size - overlap_size) + 1
    
    logger.info(f"Processing audio in {num_chunks} chunks")
    
    transcriptions = []
    start_idx = 0
    
    for i in range(num_chunks):
        end_idx = min(start_idx + chunk_size, total_samples)
        chunk = audio[start_idx:end_idx]
        
        # Skip chunks that are too short
        if len(chunk) < sample_rate:  # Skip chunks shorter than 1 second
            logger.warning(f"Skipping chunk {i+1} as it's too short")
            continue
            
        logger.info(f"Processing chunk {i+1}/{num_chunks}")
        
        try:
            # Convert to torch tensor
            audio_tensor = torch.from_numpy(chunk).to(DEVICE)
            
            # Transcribe chunk
            result = model.transcribe(
                audio_tensor,
                fp16=False,
                language='en'
            )
            
            transcription = result["text"].strip()
            if transcription:  # Only add non-empty transcriptions
                transcriptions.append(transcription)
                
            logger.info(f"Chunk {i+1} transcription: {transcription}")
            
        except Exception as e:
            logger.error(f"Error processing chunk {i+1}: {str(e)}")
            continue
            
        # Update start index for next chunk, accounting for overlap
        start_idx = end_idx - overlap_size
        
    return " ".join(transcriptions)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def process_chat_message(message: str, db: Session) -> dict:
    try:
        # Send message to Gemini
        logger.info(f"Sending message to Gemini: {message}")
        response = chat.send_message(message)
        logger.info(f"Raw Gemini response: {response.text}")
        
        # If the message is about viewing todos, handle it directly
        if any(word in message.lower() for word in ['show', 'display', 'list', 'what', 'todo', 'task', 'tomorrow']):
            # Get all todos
            todos = db.query(Todo).all()
            
            # Filter for tomorrow if requested
            if 'tomorrow' in message.lower():
                tomorrow = datetime.now().date() + timedelta(days=1)
                todos = [todo for todo in todos if todo.due_date and todo.due_date.date() == tomorrow]
                prefix = "Here are your todos for tomorrow"
            else:
                prefix = "Here are all your todos"
            
            # Format the response in a more readable way
            if todos:
                todo_list = "\n".join([
                    f"- {todo.title} (Due: {todo.due_date.strftime('%Y-%m-%d') if todo.due_date else 'No due date'})"
                    for todo in todos
                ])
                return {"reply": f"{prefix}:\n{todo_list}"}
            else:
                return {"reply": "You don't have any todos" + (" for tomorrow" if 'tomorrow' in message.lower() else " yet")}
        
        try:
            action = json.loads(response.text)
            logger.info(f"Parsed action from Gemini: {action}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {response.text}")
            return {"reply": "I apologize, but I couldn't understand how to process that. Could you please try:\n1. Using simpler phrases\n2. Breaking down your request\n3. Speaking more clearly"}
        
        if action["type"] == "output":
            return {"reply": action["output"]}

        if action["type"] == "action":
            observation = None
            
            if action["function"] == "getAllTodos":
                todos = db.query(Todo).all()
                observation = [{"id": todo.id, "title": todo.title, "due_date": todo.due_date.isoformat() if todo.due_date else None} for todo in todos]
                
                if todos:
                    todo_list = "\n".join([
                        f"- {todo.title} (Due: {todo.due_date.strftime('%Y-%m-%d') if todo.due_date else 'No due date'})"
                        for todo in todos
                    ])
                    return {"reply": f"Here are all your todos:\n{todo_list}"}
                else:
                    return {"reply": "You don't have any todos yet"}

            elif action["function"] == "createTodo":
                try:
                    input_data = action["input"]
                    due_date = None
                    
                    if input_data.get("due_date"):
                        try:
                            due_date = datetime.fromisoformat(input_data["due_date"])
                            # Validate the date is not too far in the past or future
                            today = datetime.now()
                            if due_date.year < today.year - 1 or due_date.year > today.year + 10:
                                logger.warning(f"Invalid date range: {due_date}")
                                return {"reply": "I noticed an issue with the date. Could you please specify a date within a reasonable range?"}
                        except ValueError as e:
                            logger.error(f"Date parsing error: {str(e)}")
                            return {"reply": "I had trouble understanding the date format. Could you please specify the date more clearly?"}
                    
                    new_todo = Todo(
                        title=input_data["title"],
                        due_date=due_date
                    )
                    db.add(new_todo)
                    db.commit()
                    db.refresh(new_todo)
                    observation = {"id": new_todo.id}
                    
                except KeyError as e:
                    logger.error(f"Missing required field in createTodo: {str(e)}")
                    return {"reply": "I couldn't create the todo because some required information was missing. Please make sure to specify what you want to do."}

            elif action["function"] == "searchTodo":
                search_term = action["input"]["title"]
                todos = db.query(Todo).filter(
                    Todo.title.ilike(f"%{search_term}%")
                ).all()
                
                if todos:
                    # First, let's delete the matching todo
                    for todo in todos:
                        db.delete(todo)
                    db.commit()
                    deleted_titles = [todo.title for todo in todos]
                    return {"reply": f"Deleted the following todos:\n" + "\n".join([f"- {title}" for title in deleted_titles])}
                else:
                    return {"reply": f"I couldn't find any todos matching '{search_term}'"}

            elif action["function"] == "deleteTodoById":
                todo_id = action["input"]
                if isinstance(todo_id, list):
                    # Handle bulk deletion
                    success_count = 0
                    for tid in todo_id:
                        todo = db.query(Todo).filter(Todo.id == tid).first()
                        if todo:
                            db.delete(todo)
                            success_count += 1
                    db.commit()
                    observation = {"deleted_count": success_count}
                else:
                    # Handle single deletion
                    todo = db.query(Todo).filter(Todo.id == todo_id).first()
                    if todo:
                        db.delete(todo)
                        db.commit()
                        observation = True
                    else:
                        observation = False

            try:
                # Send observation back to AI
                logger.info(f"Sending observation to Gemini: {observation}")
                follow_up = chat.send_message(json.dumps({"observation": observation}))
                follow_up_action = json.loads(follow_up.text)
                return {"reply": follow_up_action["output"]}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Gemini follow-up response: {follow_up.text}")
                return {"reply": "I've made the changes you requested, but I'm having trouble formulating a response. The action was completed successfully."}

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return {"reply": "I encountered an error while processing your request. Could you please try again or rephrase your request?"}

@app.get("/", response_class=HTMLResponse)
async def root():
    try:
        html_path = os.path.join(current_dir, "popup.html")
        if not os.path.exists(html_path):
            logger.error(f"HTML file not found at: {html_path}")
            raise HTTPException(status_code=404, detail="HTML file not found")
            
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        logger.error(f"Error serving HTML: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio_data: AudioData) -> TranscriptionResponse:
    """Transcribe audio data."""
    audio_path = None
    try:
        if not audio_data.audio:
            raise HTTPException(status_code=400, detail="No audio data received")

        audio_path = save_audio_file(audio_data.audio)
        if not audio_path:
            raise HTTPException(status_code=500, detail="Failed to save audio file")

        try:
            file_size = os.path.getsize(audio_path)
            logger.info(f"Processing file: {audio_path} (Size: {file_size} bytes)")

            logger.info("Loading audio file...")
            audio = load_audio(audio_path)
            if audio is None:
                raise HTTPException(status_code=500, detail="Failed to load audio file or audio is silent")

            if len(audio) == 0:
                raise HTTPException(status_code=400, detail="Audio file is empty")

            if not np.isfinite(audio).all():
                raise HTTPException(status_code=400, detail="Audio contains invalid values")

            # Process audio based on its length
            duration = len(audio) / 16000  # Calculate duration in seconds
            logger.info(f"Audio duration: {duration:.1f} seconds")

            try:
                if duration > 30:  # For files longer than 30 seconds
                    logger.info("Long audio detected, processing in chunks...")
                    transcription = process_audio_in_chunks(audio)
                else:
                    # Convert to torch tensor for short files
                    audio_tensor = torch.from_numpy(audio).to(DEVICE)
                    result = model.transcribe(
                        audio_tensor,
                        fp16=False,
                        language='en'
                    )
                    transcription = result["text"].strip()

                logger.info(f"Transcription result: '{transcription}'")

                if not transcription:
                    return TranscriptionResponse(
                        success=True,
                        transcription="No speech detected in the audio."
                    )

                # Process transcribed text with Gemini
                chat_response = await process_chat_message(transcription, db=get_db())
                
                return TranscriptionResponse(
                    success=True,
                    transcription=transcription,
                    chat_response=chat_response["reply"]
                )

            except Exception as e:
                logger.error(f"Error during transcription: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

        finally:
            # Delete the temporary audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info(f"Deleted temporary audio file: {audio_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {audio_path}: {e}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Deleted temporary audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {audio_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe_gemini")
async def transcribe_audio_gemini(
    audio: UploadFile = File(..., description="The audio file to transcribe"),
    db: Session = Depends(get_db)
):
    audio_path = None
    wav_path = None
    try:
        # Create temporary directory if it doesn't exist
        os.makedirs(GEMINI_TEMP_DIR, exist_ok=True)
        
        # Generate a unique filename with timestamp
        timestamp = int(time.time())
        temp_filename = f"audio_{timestamp}.webm"  
        audio_path = os.path.join(GEMINI_TEMP_DIR, temp_filename)
        wav_path = os.path.join(GEMINI_TEMP_DIR, f"audio_{timestamp}.wav")
        
        logger.info(f"Processing audio file:")
        logger.info(f"Input path: {audio_path}")
        logger.info(f"Output path: {wav_path}")
        logger.info(f"FFmpeg path: {FFMPEG_PATH}")
        
        # Save uploaded file
        contents = await audio.read()
        async with aiofiles.open(audio_path, 'wb') as out_file:
            await out_file.write(contents)
        
        logger.info(f"Audio file saved ({len(contents)} bytes)")
        
        if not os.path.exists(audio_path):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save audio file at {audio_path}"
            )
        
        # Convert WebM to WAV using ffmpeg
        logger.info("Starting FFmpeg conversion...")
        process = await asyncio.create_subprocess_exec(
            FFMPEG_PATH, '-i', audio_path, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', wav_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
            logger.error(f"FFmpeg error: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Error converting audio format: {error_msg}")
        
        if not os.path.exists(wav_path):
            raise HTTPException(
                status_code=500,
                detail=f"FFmpeg failed to create output file at {wav_path}"
            )
        
        logger.info("FFmpeg conversion successful")
        
        # Load and transcribe audio
        logger.info("Starting Whisper transcription...")
        
        if not os.path.exists(wav_path):
            raise HTTPException(
                status_code=500,
                detail=f"WAV file not found at {wav_path} before Whisper processing"
            )
            
        # Get file size and verify file
        file_size = os.path.getsize(wav_path)
        logger.info(f"WAV file size: {file_size} bytes")
        logger.info(f"WAV file absolute path: {os.path.abspath(wav_path)}")
        
        try:
            # Read the audio file directly using soundfile first to verify it
            try:
                import soundfile as sf
                audio_data, sample_rate = sf.read(wav_path)
                logger.info(f"Audio file info: {sf.info(wav_path)}")
                logger.info(f"Audio data shape from soundfile: {audio_data.shape}")
                logger.info(f"Sample rate: {sample_rate}")
                
                # Convert to float32 and normalize if needed
                audio_data = audio_data.astype(np.float32)
                if audio_data.max() > 1.0:
                    audio_data = audio_data / 32768.0  # Normalize 16-bit audio
                
                logger.info(f"Audio data type: {audio_data.dtype}")
                logger.info(f"Audio data min/max: {np.min(audio_data)}/{np.max(audio_data)}")
                
                # Try transcribing with the loaded audio data
                try:
                    result = model.transcribe(audio_data)
                    logger.info("Transcription completed")
                except Exception as transcribe_error:
                    logger.error(f"Error during transcription: {transcribe_error}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error during transcription: {str(transcribe_error)}"
                    )
                
            except Exception as sf_error:
                logger.error(f"Error reading WAV file with soundfile: {sf_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Invalid WAV file: {str(sf_error)}"
                )
            
            transcribed_text = result["text"].strip()
            logger.info(f"Transcribed text: {transcribed_text}")
            
            if not transcribed_text:
                raise HTTPException(
                    status_code=400, 
                    detail="Could not transcribe audio - no speech detected"
                )
                
            # Process transcribed text with Gemini
            logger.info("Processing with Gemini...")
            chat_response = await process_chat_message(transcribed_text, db)
            
            response_data = {
                "success": True,
                "transcription": transcribed_text,
                "chat_response": chat_response["reply"]
            }
            
            # Clean up files only after successful processing
            try:
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
                    logger.info(f"Cleaned up input file: {audio_path}")
                if wav_path and os.path.exists(wav_path):
                    os.remove(wav_path)
                    logger.info(f"Cleaned up output file: {wav_path}")
            except Exception as e:
                logger.warning(f"Error cleaning up temporary files: {str(e)}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Whisper error: {str(e)}")
            logger.error(f"Whisper error type: {type(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error during transcription: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"Error in transcribe_audio_gemini: {str(e)}")
        # Clean up files in case of error
        try:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"Cleaned up input file after error: {audio_path}")
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)
                logger.info(f"Cleaned up output file after error: {wav_path}")
        except Exception as cleanup_error:
            logger.warning(f"Error cleaning up temporary files after error: {cleanup_error}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(message: Message, db: Session = Depends(get_db)):
    return await process_chat_message(message.text, db)

@app.get("/todos")
async def get_todos(db: Session = Depends(get_db)):
    todos = db.query(Todo).all()
    return [{"id": todo.id, "title": todo.title, "due_date": todo.due_date} for todo in todos]

if __name__ == "__main__":
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
