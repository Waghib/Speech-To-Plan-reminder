import whisper
import os
import torch
import sys

# Add ffmpeg to system PATH
FFMPEG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg")
if os.path.exists(FFMPEG_PATH):
    os.environ["PATH"] = FFMPEG_PATH + os.pathsep + os.environ["PATH"]

def initialize_model(model_name="base"):
    """
    Initialize the Whisper model
    Args:
        model_name (str): Name of the model to use (tiny, base, small, medium, large)
    Returns:
        whisper.Whisper: Initialized model
    """
    try:
        model = whisper.load_model(model_name)
        return model
    except Exception as e:
        print(f"Error loading model: {str(e)}")
        return None

def transcribe_audio(model, audio_path, language=None):
    """
    Transcribe audio file to text
    Args:
        model: Whisper model instance
        audio_path (str): Path to audio file
        language (str, optional): Language code for transcription
    Returns:
        str: Transcribed text
    """
    try:
        # Load audio and get transcription
        result = model.transcribe(
            audio_path,
            language=language,
            fp16=torch.cuda.is_available()  # Use GPU if available
        )
        return result["text"]
    except Exception as e:
        print(f"Error transcribing audio: {str(e)}")
        return None

def detect_language(model, audio_path):
    """
    Detect the language of the audio
    Args:
        model: Whisper model instance
        audio_path (str): Path to audio file
    Returns:
        str: Detected language code
    """
    try:
        # Load audio
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        
        # Make log-Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio).to(model.device)
        
        # Detect language
        _, probs = model.detect_language(mel)
        detected_lang = max(probs, key=probs.get)
        return detected_lang
    except Exception as e:
        print(f"Error detecting language: {str(e)}")
        return None

def main():
    # Check if ffmpeg is available
    if not os.path.exists(FFMPEG_PATH):
        print("Error: ffmpeg not found in the ffmpeg directory!")
        print("Please download ffmpeg and place it in the 'ffmpeg' folder.")
        return

    # Initialize model (using 'base' model for better performance)
    print("Loading Whisper model...")
    model = initialize_model("base")
    
    if model is None:
        print("Failed to load model. Exiting...")
        return

    # Example usage
    audio_file = "audio1.mp3"  # Replace with your audio file
    
    if not os.path.exists(audio_file):
        print(f"Audio file {audio_file} not found!")
        print("Please place an audio file in the project directory and update the audio_file variable.")
        return
    
    print("\nDetecting language...")
    detected_lang = detect_language(model, audio_file)
    if detected_lang:
        print(f"Detected language: {detected_lang}")
    
    print("\nTranscribing audio...")
    transcription = transcribe_audio(model, audio_file, language=detected_lang)
    if transcription:
        print("\nTranscription:")
        print(transcription)

if __name__ == "__main__":
    main()