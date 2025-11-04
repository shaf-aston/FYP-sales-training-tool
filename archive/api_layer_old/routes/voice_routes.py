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

from services.tts_service import get_tts_service
from services.stt_service import get_stt_service
from services.chat_service import chat_service
from services.model_service import model_service

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
        stt_service = get_stt_service()
        
        # Read audio file
        audio_bytes = await audio.read()
        
        # Validate audio
        validation = stt_service.validate_audio(audio_bytes)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid audio: {', '.join(validation['issues'])}"
            )
        
        # Transcribe audio
        result = stt_service.transcribe_audio(audio_bytes, language=language)
        
        if result is None or not result.text:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")
        
        return {
            "text": result.text,
            "confidence": result.confidence,
            "language": result.language,
            "duration": result.duration,
            "processing_time": result.processing_time,
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
        output_format = payload.get("format", "wav")
        
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Get TTS service
        tts_service = get_tts_service()
        
        # Generate speech
        logger.info(f"Generating TTS for persona '{persona_name}': {text[:50]}...")
        audio_bytes = tts_service.synthesize_speech(text, persona_name, output_format)
        
        if audio_bytes is None or len(audio_bytes) == 0:
            raise HTTPException(status_code=500, detail="Failed to generate speech")
        
        # Return audio stream
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
    """Complete voice conversation: audio -> STT -> AI chat -> TTS -> audio
    
    Args:
        audio: Audio file with user's speech
        user_id: User identifier for conversation context
        persona_name: Persona to chat with (Mary, Jake, Sarah, David)
        session_id: Session ID for conversation continuity
        
    Returns:
        {
            "user_text": "transcribed user speech",
            "ai_response": "AI text response",
            "ai_audio_base64": "base64 encoded audio",
            "confidence": 0.95,
            "session_id": "session-id",
            "status": "success"
        }
    """
    try:
        # Get services
        stt_service = get_stt_service()
        tts_service = get_tts_service()
        
        # Step 1: Convert speech to text (STT)
        logger.info(f"Processing voice chat for user {user_id}")
        audio_bytes = await audio.read()
        
        stt_result = stt_service.transcribe_audio(audio_bytes)
        if stt_result is None or not stt_result.text:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")
        
        user_text = stt_result.text
        logger.info(f"Transcribed: {user_text}")
        
        # Step 2: Get AI response
        pipe = model_service.get_pipeline()
        chat_result = chat_service.chat_with_persona(
            message=user_text,
            user_id=user_id,
            persona_name=persona_name,
            pipe=pipe,
            session_id=session_id
        )
        
        ai_response = chat_result.get("response", "I apologize, I'm having trouble responding.")
        session_id = chat_result.get("session_id")
        
        # Step 3: Convert AI response to speech (TTS)
        ai_audio_base64 = None
        try:
            ai_audio_bytes = tts_service.synthesize_speech(ai_response, persona_name)
            if ai_audio_bytes:
                ai_audio_base64 = base64.b64encode(ai_audio_bytes).decode('utf-8')
        except Exception as tts_error:
            logger.warning(f"TTS generation failed: {tts_error}")
            # Continue without audio - user still gets text response
        
        return {
            "user_text": user_text,
            "ai_response": ai_response,
            "ai_audio_base64": ai_audio_base64,
            "confidence": stt_result.confidence,
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
        stt_service = get_stt_service()
        tts_service = get_tts_service()
        
        stt_stats = stt_service.get_stats()
        tts_stats = tts_service.get_stats()
        
        return {
            "stt": {
                "available": stt_stats["whisper_available"] or stt_stats["speech_recognition_available"],
                "backend": stt_stats["primary_backend"],
                "gpu_enabled": stt_stats["gpu_enabled"],
                "transcriptions": stt_stats["transcriptions"],
                "cache_hit_rate": round(stt_stats["cache_hit_rate"], 2),
                "avg_processing_time": round(stt_stats["average_processing_time"], 3)
            },
            "tts": {
                "available": len(tts_stats["loaded_models"]) > 0 or tts_service is not None,
                "gpu_enabled": tts_stats["gpu_enabled"],
                "loaded_models": tts_stats["loaded_models"],
                "generations": tts_stats["generations"],
                "cache_hit_rate": round(tts_stats["cache_hit_rate"], 2),
                "avg_generation_time": round(tts_stats["average_generation_time"], 3)
            },
            "available_voices": tts_service.get_available_voices(),
            "supported_languages": stt_service.get_supported_languages(),
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