import os
import base64
import logging
import numpy as np
import torch
import whisper
import soundfile as sf
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tempfile import gettempdir
import uvicorn
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
TEMP_DIR = os.path.join(gettempdir(), 'audio_transcription')
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Create temp directory if it doesn't exist
os.makedirs(TEMP_DIR, exist_ok=True)

# Load Whisper model
logger.info(f"Loading Whisper model on {DEVICE}...")
model = whisper.load_model("base")
model.to(DEVICE)

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

class AudioData(BaseModel):
    audio: str

class TranscriptionResponse(BaseModel):
    success: bool
    transcription: Optional[str] = None
    error: Optional[str] = None

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
            'ffmpeg/ffmpeg.exe',
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

                return TranscriptionResponse(
                    success=True,
                    transcription=transcription
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

if __name__ == '__main__':
    logger.info(f"Server starting. Temp directory: {TEMP_DIR}")
    uvicorn.run(app, host="127.0.0.1", port=5000)
