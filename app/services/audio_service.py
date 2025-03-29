"""
Audio processing service for the Speech-To-Plan Reminder application.
"""

import os
import base64
import logging
import numpy as np
import subprocess
import soundfile as sf
from typing import Optional

from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

def save_audio_file(audio_data: str) -> Optional[str]:
    """
    Save base64 audio data to a temporary file.
    
    Args:
        audio_data: Base64 encoded audio data
        
    Returns:
        Path to saved file or None if failed
    """
    try:
        # Remove data URL prefix if present
        if 'base64,' in audio_data:
            audio_data = audio_data.split('base64,')[1]

        # Decode base64 data
        audio_bytes = base64.b64decode(audio_data)

        # Create temporary file
        temp_path = os.path.join(settings.TEMP_DIR, f'temp_audio_{os.urandom(8).hex()}.mp3')
        
        with open(temp_path, 'wb') as f:
            f.write(audio_bytes)
        
        return temp_path
    except Exception as e:
        logger.error(f"Error saving audio file: {str(e)}")
        return None

def process_audio_file(file_path: str) -> Optional[np.ndarray]:
    """
    Process audio file and convert to required format.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        Processed audio as numpy array or None if failed
    """
    try:
        # Convert audio to WAV format with required specifications
        output_path = file_path.rsplit('.', 1)[0] + '_converted.wav'
        
        # FFmpeg command to convert audio to the required format
        command = [
            str(settings.FFMPEG_PATH),
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
            text=True
        )
        
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr}")
            return None
        
        # Load converted audio file
        audio, _ = sf.read(output_path)
        
        # Clean up temporary files
        try:
            os.remove(output_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {output_path}: {str(e)}")
        
        return audio
    except Exception as e:
        logger.error(f"Error processing audio file: {str(e)}")
        return None

def process_audio_in_chunks(audio: np.ndarray, chunk_duration: int = 30, overlap: int = 1) -> list:
    """
    Process long audio files in chunks.
    
    Args:
        audio: Audio data as numpy array
        chunk_duration: Duration of each chunk in seconds
        overlap: Overlap between chunks in seconds
        
    Returns:
        List of audio chunks
    """
    try:
        # Calculate chunk size and overlap in samples
        sample_rate = 16000  # Assuming 16kHz sample rate
        chunk_size = chunk_duration * sample_rate
        overlap_size = overlap * sample_rate
        
        # Calculate number of chunks
        audio_length = len(audio)
        num_chunks = max(1, int(np.ceil((audio_length - overlap_size) / (chunk_size - overlap_size))))
        
        chunks = []
        for i in range(num_chunks):
            # Calculate start and end indices
            start = i * (chunk_size - overlap_size)
            end = min(start + chunk_size, audio_length)
            
            # Extract chunk
            chunk = audio[start:end]
            chunks.append(chunk)
            
            # Break if we've reached the end of the audio
            if end == audio_length:
                break
        
        return chunks
    except Exception as e:
        logger.error(f"Error processing audio in chunks: {str(e)}")
        return [audio]  # Return the original audio as a single chunk
