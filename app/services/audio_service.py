"""
Audio service for the Speech-To-Plan Reminder application.
"""

import base64
import logging
import os
import numpy as np
import whisper
from typing import Optional

from app.config import TEMP_DIR, DEVICE, WHISPER_MODEL

# Configure logging
logger = logging.getLogger(__name__)

# Load Whisper model
logger.info(f"Loading Whisper model on {DEVICE}...")
model = whisper.load_model(WHISPER_MODEL)
model.to(DEVICE)

def save_audio_file(audio_data: str) -> Optional[str]:
    """
    Save base64 audio data to a temporary file.
    
    Args:
        audio_data: Base64 encoded audio data
        
    Returns:
        Path to saved audio file or None if error
    """
    try:
        # Remove data URL prefix if present
        if 'base64,' in audio_data:
            audio_data = audio_data.split('base64,')[1]
        
        # Decode base64 data
        audio_bytes = base64.b64decode(audio_data)
        
        # Create temporary file
        os.makedirs(TEMP_DIR, exist_ok=True)
        temp_path = os.path.join(TEMP_DIR, f'temp_audio_{os.urandom(8).hex()}.mp3')
        
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        return temp_path
    except Exception as e:
        logger.error(f"Error saving audio file: {str(e)}")
        return None

def process_audio_file(file_path: str) -> Optional[np.ndarray]:
    """
    Process audio file and return numpy array.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Processed audio as numpy array or None if error
    """
    try:
        # Load audio using whisper's load_audio function
        audio = whisper.load_audio(file_path)
        
        # Check if audio is valid
        if audio is None or len(audio) == 0:
            logger.error("Audio file is empty or invalid")
            return None
        
        if not np.isfinite(audio).all():
            logger.error("Audio contains invalid values")
            return None
        
        return audio
    except Exception as e:
        logger.error(f"Error processing audio file: {str(e)}")
        return None

def transcribe_audio(audio: np.ndarray) -> str:
    """
    Transcribe audio using Whisper.
    
    Args:
        audio: Audio data as numpy array
        
    Returns:
        Transcribed text
    """
    try:
        # Transcribe audio
        result = model.transcribe(audio)
        
        return result["text"].strip()
    except Exception as e:
        logger.error(f"Error transcribing audio: {str(e)}")
        raise
