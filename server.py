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

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        # Get audio data from request
        audio_data = request.json.get('audio')
        if not audio_data:
            logger.error("No audio data received")
            return jsonify({'error': 'No audio data received'}), 400

        # Save the audio file
        audio_path = save_audio_file(audio_data)
        if not audio_path:
            return jsonify({'error': 'Failed to save audio file'}), 500

        try:
            # Log file details
            file_size = os.path.getsize(audio_path)
            logger.info(f"Processing file: {audio_path} (Size: {file_size} bytes)")

            # Load audio using ffmpeg
            logger.info("Loading audio file...")
            audio = load_audio(audio_path)
            if audio is None:
                return jsonify({'error': 'Failed to load audio file or audio is silent'}), 500

            # Ensure audio is not empty and has valid values
            if len(audio) == 0:
                return jsonify({'error': 'Audio file is empty'}), 400

            if not np.isfinite(audio).all():
                return jsonify({'error': 'Audio contains invalid values'}), 400

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio).to(DEVICE)

            # Transcribe audio
            logger.info("Starting transcription...")
            result = model.transcribe(
                audio_tensor,
                fp16=False,
                language='en'
            )

            transcription = result["text"].strip()
            logger.info(f"Transcription result: '{transcription}'")

            # Log confidence scores if available
            if "segments" in result:
                for segment in result["segments"]:
                    logger.debug(f"Segment confidence: {segment.get('confidence', 'N/A')}")

            return jsonify({
                'success': True,
                'transcription': transcription if transcription else "No speech detected in the audio."
            })

        except Exception as e:
            logger.error(f"Error during transcription: {str(e)}", exc_info=True)
            return jsonify({'error': str(e)}), 500

        finally:
            # Keep the file for debugging, but log its presence
            logger.info(f"Debug: Audio file remains at {audio_path}")

    except Exception as e:
        logger.error(f"Server error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Server starting. Temp directory: {TEMP_DIR}")
    app.run(host='127.0.0.1', port=5000, debug=True)
