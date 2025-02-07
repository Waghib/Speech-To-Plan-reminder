from flask import Flask, request, jsonify
from flask_cors import CORS
import whisper
import base64
import logging
import os
import numpy as np
import time
import subprocess
import torch
import soundfile as sf

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Create temp directory
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_files')
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
    logger.info(f"Created temp directory at {TEMP_DIR}")

# Initialize Whisper model
logger.info("Loading Whisper model...")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model("base").to(DEVICE)

def load_audio(file_path):
    """Load and preprocess audio file using ffmpeg."""
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

def save_audio_file(base64_audio):
    """Save audio file and return the path."""
    try:
        # Create a unique filename
        timestamp = int(time.time())
        file_path = os.path.join(TEMP_DIR, f'audio_{timestamp}.mp3')
        
        # Extract the actual base64 content
        if ',' in base64_audio:
            header, encoded = base64_audio.split(",", 1)
            logger.debug(f"Audio header: {header}")
        else:
            encoded = base64_audio
            
        # Decode base64 data
        audio_bytes = base64.b64decode(encoded)
        logger.debug(f"Decoded audio size: {len(audio_bytes)} bytes")
        
        # Save the file
        with open(file_path, 'wb') as f:
            f.write(audio_bytes)
        
        # Verify file was created
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            logger.info(f"Saved audio file: {file_path} (Size: {file_size} bytes)")
            return file_path
        else:
            logger.error(f"File was not created: {file_path}")
            return None
            
    except Exception as e:
        logger.error(f"Error saving audio file: {str(e)}")
        return None

def process_audio_in_chunks(audio, chunk_duration=30, overlap=1):
    """Process long audio files in chunks."""
    sample_rate = 16000  # Whisper's expected sample rate
    chunk_length = chunk_duration * sample_rate
    overlap_length = overlap * sample_rate
    
    if len(audio) <= chunk_length:
        return model.transcribe(audio, fp16=False, language='en')["text"]
        
    full_transcript = []
    position = 0
    total_chunks = (len(audio) - overlap_length) // (chunk_length - overlap_length)
    chunk_number = 0
    
    while position < len(audio):
        chunk_number += 1
        end = min(position + chunk_length, len(audio))
        chunk = audio[position:end]
        
        # Skip if chunk is too short
        if len(chunk) < sample_rate * 2:  # Skip if less than 2 seconds
            break
            
        logger.info(f"Processing chunk {chunk_number}/{total_chunks} - {position/sample_rate:.1f}s to {end/sample_rate:.1f}s")
        try:
            result = model.transcribe(chunk, fp16=False, language='en')
            transcript = result["text"].strip()
            
            if transcript:  # Only add non-empty transcriptions
                full_transcript.append(transcript)
                
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_number}: {str(e)}")
            
        # Move to next chunk, ensuring we make forward progress
        next_position = position + (chunk_length - overlap_length)
        if next_position <= position:  # Ensure we always move forward
            next_position = position + chunk_length
        position = next_position
        
    return " ".join(full_transcript)

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    audio_path = None
    try:
        audio_data = request.json.get('audio')
        if not audio_data:
            logger.error("No audio data received")
            return jsonify({'success': False, 'error': 'No audio data received'}), 400

        audio_path = save_audio_file(audio_data)
        if not audio_path:
            return jsonify({'success': False, 'error': 'Failed to save audio file'}), 500

        try:
            file_size = os.path.getsize(audio_path)
            logger.info(f"Processing file: {audio_path} (Size: {file_size} bytes)")

            logger.info("Loading audio file...")
            audio = load_audio(audio_path)
            if audio is None:
                return jsonify({'success': False, 'error': 'Failed to load audio file or audio is silent'}), 500

            if len(audio) == 0:
                return jsonify({'success': False, 'error': 'Audio file is empty'}), 400

            if not np.isfinite(audio).all():
                return jsonify({'success': False, 'error': 'Audio contains invalid values'}), 400

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
                    return jsonify({
                        'success': True,
                        'transcription': "No speech detected in the audio."
                    })

                return jsonify({
                    'success': True,
                    'transcription': transcription
                })

            except Exception as e:
                logger.error(f"Error during transcription: {str(e)}")
                return jsonify({'success': False, 'error': f'Transcription error: {str(e)}'}), 500

        finally:
            # Delete the temporary audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info(f"Deleted temporary audio file: {audio_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {audio_path}: {e}")

    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Deleted temporary audio file: {audio_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file {audio_path}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Server starting. Temp directory: {TEMP_DIR}")
    app.run(host='127.0.0.1', port=5000, debug=True)
