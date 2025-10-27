"""
Voice API routes for speech-to-text and text-to-speech
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import io
import logging
from typing import Optional

from services.voice_service import get_voice_service
from services.chat_service import chat_service
from services.model_service import model_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/voice", tags=["voice"])

@router.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """Convert uploaded audio to text using Whisper
    
    Args:
        audio: Audio file (wav, mp3, etc.)
        
    Returns:
        {"text": "transcribed text", "status": "success"}
    """
    try:
        voice_service = get_voice_service()
        if not voice_service.is_available()["whisper"]:
            raise HTTPException(status_code=503, detail="Speech-to-text service not available")
        
        # Read audio file
        audio_bytes = await audio.read()
        
        # Convert to text
        text = await voice_service.speech_to_text(audio_bytes)
        
        if text is None:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")
        
        return {
            "text": text,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Speech-to-text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/text-to-speech")
async def text_to_speech(payload: dict):
    """Convert text to speech using ElevenLabs
    
    Args:
        payload: {"text": "text to convert", "voice_id": "optional_voice_id"}
        
    Returns:
        Audio stream
    """
    try:
        text = payload.get("text", "")
        voice_id = payload.get("voice_id")
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        voice_service = get_voice_service()
        if not voice_service.is_available()["elevenlabs"]:
            raise HTTPException(status_code=503, detail="Text-to-speech service not available")
        
        # Convert to speech
        audio_bytes = await voice_service.text_to_speech(text, voice_id)
        
        if audio_bytes is None:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
        
        # Return audio stream
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"}
        )
        
    except Exception as e:
        logger.error(f"Text-to-speech error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/voice-chat")
async def voice_chat(audio: UploadFile = File(...), user_id: Optional[str] = "default"):
    """Complete voice conversation: audio -> text -> AI response -> audio
    
    Args:
        audio: Audio file with user's speech
        user_id: User identifier for conversation context
        
    Returns:
        {
            "user_text": "transcribed user speech",
            "ai_response": "AI text response", 
            "ai_audio": "base64 encoded audio",
            "status": "success"
        }
    """
    try:
        # Check service availability
        voice_service = get_voice_service()
        availability = voice_service.is_available()
        if not availability["whisper"]:
            raise HTTPException(status_code=503, detail="Speech-to-text not available")
        
        # Step 1: Convert speech to text
        audio_bytes = await audio.read()
        user_text = await voice_service.speech_to_text(audio_bytes)
        
        if user_text is None:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")
        
        # Step 2: Get AI response
        pipe = model_service.get_pipeline()
        ai_response = chat_service.chat_with_mary(user_text, user_id, pipe)
        
        # Step 3: Convert AI response to speech (if TTS available)
        ai_audio = None
        if availability["elevenlabs"]:
            ai_audio_bytes = await voice_service.text_to_speech(ai_response)
            if ai_audio_bytes:
                import base64
                ai_audio = base64.b64encode(ai_audio_bytes).decode('utf-8')
        
        return {
            "user_text": user_text,
            "ai_response": ai_response,
            "ai_audio": ai_audio,
            "status": "success",
            "context_size": len(chat_service.conversation_contexts.get(f"{user_id}_mary", []))
        }
        
    except Exception as e:
        logger.error(f"Voice chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def voice_status():
    """Check voice service availability"""
    voice_service = get_voice_service()
    availability = voice_service.is_available()
    return {
        "whisper_available": availability["whisper"],
        "elevenlabs_available": availability["elevenlabs"],
        "services": {
            "speech_to_text": "ready" if availability["whisper"] else "unavailable",
            "text_to_speech": "ready" if availability["elevenlabs"] else "unavailable"
        }
    }