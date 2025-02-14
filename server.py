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
from calendar_service import create_calendar_event

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

Example interaction for adding a task:
User: "Add buy groceries to my list"
Assistant: { "type": "action", "function": "createTodo", "input": "Buy groceries" }
System: { "observation": 1 }
Assistant: { "type": "output", "output": "I've added 'Buy groceries' to your todo list" }

Example interaction for listing tasks:
User: "Show my tasks"
Assistant: { "type": "action", "function": "getAllTodos", "input": "" }
System: { "observation": [{"id": 1, "todo": "Buy groceries"}] }
Assistant: { "type": "output", "output": "Here are your tasks:\\n1. Buy groceries" }

Example interaction for deleting a task:
User: "Remove the groceries task"
Assistant: { "type": "action", "function": "getAllTodos", "input": "" }
System: { "observation": [{"id": 1, "todo": "Buy groceries"}] }
Assistant: { "type": "action", "function": "deleteTodoById", "input": 1 }
System: { "observation": null }
Assistant: { "type": "output", "output": "I've removed 'Buy groceries' from your todo list" }
"""

# Initialize chat
chat = gemini_model.start_chat(history=[
    {"role": "user", "parts": [SYSTEM_PROMPT]},
])

# Create FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files from extension directory
extension_dir = os.path.join(os.path.dirname(__file__), "extension")
app.mount("/static", StaticFiles(directory=extension_dir), name="static")

@app.get("/")
async def root():
    """Serve the main popup.html from extension directory"""
    return FileResponse(os.path.join(extension_dir, "popup.html"))

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

async def process_chat_message(message: str, db: Session):
    try:
        # Send message to Gemini
        logger.info(f"Sending message to Gemini: {message}")
        response = chat.send_message(message)
        response_text = response.text
        logger.info(f"Raw Gemini response: {response_text}")
        
        try:
            response_json = json.loads(response_text)
            
            # If it's a direct output response, return it immediately
            if response_json["type"] == "output":
                return {"reply": response_json["output"]}
            
            # Handle action responses
            if response_json["type"] == "action":
                observation = None
                
                if response_json["function"] == "createTodo":
                    input_data = response_json["input"]
                    title = input_data.get("title", "")
                    due_date = input_data.get("due_date")
                    
                    # Create todo in database
                    todo = Todo(todo=title)
                    if due_date:
                        todo.due_date = datetime.strptime(due_date, "%Y-%m-%d")
                    
                    db.add(todo)
                    db.commit()
                    db.refresh(todo)
                    
                    # Add event to Google Calendar if due date is provided
                    if due_date:
                        try:
                            calendar_event_id = create_calendar_event(title, due_date)
                            if calendar_event_id:
                                todo.calendar_event_id = calendar_event_id
                                db.commit()
                                return {"reply": f"Added '{title}' to your todo list and created a calendar event for {due_date}"}
                        except Exception as e:
                            logger.error(f"Error creating calendar event: {str(e)}")
                            return {"reply": f"Added '{title}' to your todo list, but failed to create calendar event: {str(e)}"}
                    
                    return {"reply": f"Added '{title}' to your todo list"}
                
                elif response_json["function"] == "getAllTodos":
                    todos = db.query(Todo).all()
                    if todos:
                        todo_list = "\n".join([
                            f"- {todo.todo} (Due: {todo.due_date.strftime('%Y-%m-%d') if todo.due_date else 'No due date'})"
                            for todo in todos
                        ])
                        return {"reply": f"Here are all your todos:\n{todo_list}"}
                    else:
                        return {"reply": "You don't have any todos yet"}
                
                elif response_json["function"] == "searchTodo":
                    search_term = response_json["input"]["title"]
                    todos = db.query(Todo).filter(
                        Todo.todo.ilike(f"%{search_term}%")
                    ).all()
                    
                    if todos:
                        # First, let's delete the matching todo
                        for todo in todos:
                            db.delete(todo)
                        db.commit()
                        deleted_titles = [todo.todo for todo in todos]
                        return {"reply": f"Deleted the following todos:\n" + "\n".join([f"- {title}" for title in deleted_titles])}
                    else:
                        return {"reply": f"I couldn't find any todos matching '{search_term}'"}
                
                elif response_json["function"] == "deleteTodoById":
                    todo_id = response_json["input"]
                    if isinstance(todo_id, list):
                        # Handle bulk deletion
                        success_count = 0
                        for tid in todo_id:
                            todo = db.query(Todo).filter(Todo.id == tid).first()
                            if todo:
                                db.delete(todo)
                                success_count += 1
                        db.commit()
                        return {"reply": f"Successfully deleted {success_count} todos"}
                    else:
                        # Handle single deletion
                        todo = db.query(Todo).filter(Todo.id == todo_id).first()
                        if todo:
                            db.delete(todo)
                            db.commit()
                            return {"reply": f"Successfully deleted todo"}
                        else:
                            return {"reply": "Could not find the todo to delete"}

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {response_text}")
            return {"reply": "I apologize, but I couldn't understand how to process that. Could you please try:\n1. Using simpler phrases\n2. Breaking down your request\n3. Speaking more clearly"}

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return {"reply": "I encountered an error while processing your request. Could you please try again or rephrase your request?"}

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
                raise HTTPException(
                    status_code=500,
                    detail=f"Transcription error: {str(e)}"
                )

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
    return [{"id": todo.id, "title": todo.todo, "due_date": todo.due_date.isoformat() if todo.due_date else None} for todo in todos]

if __name__ == "__main__":
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
