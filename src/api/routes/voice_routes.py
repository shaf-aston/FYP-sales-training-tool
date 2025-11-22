"""
Voice API routes for speech-to-text and text-to-speech
Integrated with Coqui TTS and Whisper STT for high-quality voice interactions
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, Response
import io
import logging
import base64
from typing import Optional

from src.services.voice_services import get_tts_service
from src.services.voice_services import get_stt_service
from src.services.ai_services import chat_service
from src.services.ai_services import model_service
from src.services.voice_services import get_voice_service, VoiceEmotion

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["voice"])

@router.post("/stt")
async def speech_to_text(audio: UploadFile = File(...), language: Optional[str] = "en"):
    """Convert uploaded audio to text using Whisper STT
    
    Args:
        audio: Audio file (wav, mp3, m4a, etc.)
        language: Expected language code (default: "en")
        
    Returns:
        {
            "text": "transcribed text",
            "confidence": 0.95,
            "language": "en",
            "duration": 3.5,
            "status": "success"
        }
    """
    try:
        voice_service = get_voice_service()
        
        audio_bytes = await audio.read()
        
        vs_result = await voice_service.speech_to_text(audio_bytes, language=language)
        
        if not vs_result or not vs_result.get("text"):
            raise HTTPException(status_code=500, detail="Failed to transcribe audio using voice service")

        return {
            "text": vs_result.get("text"),
            "confidence": vs_result.get("confidence"),
            "language": vs_result.get("language", language),
            "duration": vs_result.get("duration"),
            "processing_time": vs_result.get("processing_time"),
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech-to-text error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"STT error: {str(e)}")

@router.post("/tts")
async def text_to_speech(payload: dict):
    """Convert text to speech using Coqui TTS with persona-specific voices
    
    Args:
        payload: {
            "text": "text to convert",
            "persona_name": "Mary" (optional, default: "System"),
            "format": "wav" (optional)
        }
        
    Returns:
        Audio stream (WAV format)
    """
    try:
        text = payload.get("text", "")
        persona_name = payload.get("persona_name", "System")
        
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        voice_service = get_voice_service()
        
        # Use persona_name as speaker_voice, default to "System"
        speaker_voice = persona_name if persona_name else "System"
        emotion = VoiceEmotion.FRIENDLY
        audio_bytes = await voice_service.text_to_speech(text, emotion, speaker_voice=speaker_voice)
        
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
        
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=speech_{persona_name}.wav",
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text-to-speech error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")

@router.post("/voice-chat")
async def voice_chat(
    audio: UploadFile = File(...),
    user_id: Optional[str] = "default",
    persona_name: Optional[str] = "Mary",
    session_id: Optional[str] = None
):
    """Complete voice conversation: audio -> STT -> AI chat -> TTS -> audio"""
    try:
        voice_service = get_voice_service()
        
        logger.info(f"Processing voice chat for user {user_id}")
        audio_bytes = await audio.read()
        
        stt_result = await voice_service.speech_to_text(audio_bytes)
        if not stt_result or not stt_result.get("text"):
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")
        
        user_text = stt_result.get("text")
        stt_confidence = stt_result.get("confidence")
        logger.info(f"Transcribed: {user_text}")
        
        pipe = await model_service.get_pipeline()
        chat_result = chat_service.chat_with_persona(
            message=user_text,
            user_id=user_id,
            persona_name=persona_name,
            pipe=pipe,
            session_id=session_id
        )
        
        ai_response = chat_result.get("response", "I apologize, I'm having trouble responding.")
        session_id = chat_result.get("session_id")
        
        # Use persona_name for TTS voice
        ai_audio_bytes = await voice_service.text_to_speech(
            ai_response, 
            VoiceEmotion.FRIENDLY, 
            speaker_voice=persona_name if persona_name else "System"
        )
        ai_audio_base64 = base64.b64encode(ai_audio_bytes).decode('utf-8') if ai_audio_bytes else None
        
        return {
            "user_text": user_text,
            "ai_response": ai_response,
            "ai_audio_base64": ai_audio_base64,
            "confidence": stt_confidence,
            "session_id": session_id,
            "persona_name": persona_name,
            "message_count": chat_result.get("message_count", 0),
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Voice chat error: {str(e)}")

@router.get("/voice-status")
async def voice_status():
    """Check TTS and STT service availability and statistics"""
    try:
        voice_service = get_voice_service()
        capabilities = voice_service.get_voice_capabilities()
        
        return {
            "stt": {
                "available": capabilities.get("stt", {}).get("available"),
                "backend": capabilities.get("stt", {}).get("backend"),
                "gpu_enabled": capabilities.get("stt", {}).get("gpu_enabled"),
                "details": capabilities.get("stt", {}).get("details")
            },
            "tts": {
                "available": capabilities.get("tts", {}).get("available"),
                "backend": capabilities.get("tts", {}).get("backend"),
                "gpu_enabled": capabilities.get("tts", {}).get("gpu_enabled"),
                "details": capabilities.get("tts", {}).get("details")
            },
            "available_voices": capabilities.get("available_voices", {}),
            "supported_languages": capabilities.get("supported_languages", []),
            "status": "ready"
        }
    except Exception as e:
        logger.error(f"Error getting voice status: {e}")
        return {
            "stt": {"available": False},
            "tts": {"available": False},
            "status": "error",
            "error": str(e)
        }