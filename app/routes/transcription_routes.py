"""
Transcription routes for the Speech-To-Plan Reminder application.
"""

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import os
import json

from app.models.todo import get_db
from app.services.audio_service import process_audio_file, save_audio_file, transcribe_audio
from app.services.ai_service import process_chat_message
from app.config import EXTENSION_DIR

router = APIRouter(tags=["transcription"])

class AudioData(BaseModel):
    """Audio data model for base64 encoded audio."""
    audio: str

class TranscriptionResponse(BaseModel):
    """Response model for transcription endpoints."""
    success: bool
    transcription: Optional[str] = None
    chat_response: Optional[str] = None
    error: Optional[str] = None

class Message(BaseModel):
    """Message model for chat endpoints."""
    text: str

@router.get("/")
async def root():
    """Serve the main popup.html from extension directory."""
    return FileResponse(os.path.join(EXTENSION_DIR, "popup.html"))

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio_endpoint(audio_data: AudioData):
    """Transcribe audio using Whisper."""
    try:
        # Save audio file
        temp_path = save_audio_file(audio_data.audio)
        if not temp_path:
            raise HTTPException(status_code=400, detail="Failed to save audio file")
        
        # Process audio file
        audio = process_audio_file(temp_path)
        if audio is None:
            raise HTTPException(status_code=400, detail="Failed to process audio file")
        
        # Transcribe audio
        transcription = transcribe_audio(audio)
        
        return TranscriptionResponse(
            success=True,
            transcription=transcription
        )
    except Exception as e:
        return TranscriptionResponse(
            success=False,
            error=str(e)
        )

@router.post("/transcribe_gemini", response_model=TranscriptionResponse)
async def transcribe_audio_gemini_endpoint(
    audio: UploadFile = File(..., description="The audio file to transcribe"),
    db: Session = Depends(get_db)
):
    """Transcribe audio using Gemini and process as chat message."""
    try:
        # Save uploaded file
        temp_path = f"temp_files/temp_audio_{os.urandom(8).hex()}.mp3"
        with open(temp_path, "wb") as buffer:
            buffer.write(await audio.read())
        
        # Process audio file
        processed_audio = process_audio_file(temp_path)
        if processed_audio is None:
            raise HTTPException(status_code=400, detail="Failed to process audio file")
        
        # Transcribe audio
        transcription = transcribe_audio(processed_audio)
        
        # Process transcription as chat message
        chat_response = await process_chat_message(transcription, db)
        
        # Check if the response is a JSON string and extract the actual message
        try:
            response_json = json.loads(chat_response)
            if isinstance(response_json, dict) and "output" in response_json:
                chat_response = response_json["output"]
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON or doesn't have the expected structure, keep as is
            pass
        
        return TranscriptionResponse(
            success=True,
            transcription=transcription,
            chat_response=chat_response
        )
    except Exception as e:
        return TranscriptionResponse(
            success=False,
            error=str(e)
        )

@router.post("/chat", response_model=dict)
async def chat_endpoint(message: Message, db: Session = Depends(get_db)):
    """Handle text-based chat messages from the frontend."""
    try:
        response = await process_chat_message(message.text, db)
        
        # Check if the response is a JSON string and extract the actual message
        try:
            response_json = json.loads(response)
            if isinstance(response_json, dict) and "output" in response_json:
                response = response_json["output"]
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON or doesn't have the expected structure, keep as is
            pass
            
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
