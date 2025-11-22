"""
Backward compatibility layer for voice services
Maintains existing API while using new simplified services
"""
import logging
from typing import Dict, Any, Optional, Union

from ..voice import VoiceService, create_voice_service
from src.models.tts.models import VoiceProfile, VoiceEmotion

logger = logging.getLogger(__name__)

# Global service instances for backward compatibility
_voice_service = None
_stt_service = None
_tts_service = None

def get_voice_service():
    """Get or create voice service instance"""
    global _voice_service
    if _voice_service is None:
        _voice_service = create_voice_service()
    return _voice_service

def get_stt_service():
    """Get STT service for backward compatibility"""
    return get_voice_service().stt_service

def get_tts_service():
    """Get TTS service for backward compatibility"""
    return get_voice_service().tts_service

# Legacy class for backward compatibility
class EnhancedVoiceService:
    """Legacy voice service interface"""
    
    def __init__(self):
        self.voice_service = get_voice_service()
    
    async def speech_to_text(self, audio_data: bytes, language: str = "en") -> Dict[str, Any]:
        """Legacy STT method"""
        try:
            result = self.voice_service.transcribe(audio_data, language)
            return {
                "text": result.text,
                "confidence": result.confidence,
                "language": result.language,
                "duration": result.duration,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"STT failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "duration": 0.0,
                "status": "error",
                "error": str(e)
            }
    
    async def text_to_speech(self, text: str, 
                           voice_emotion: Union[str, VoiceEmotion] = "neutral",
                           persona_name: str = "default") -> Dict[str, Any]:
        """Legacy TTS method"""
        try:
            # Create voice profile from legacy parameters
            if isinstance(voice_emotion, str):
                emotion = VoiceEmotion(voice_emotion) if voice_emotion in [e.value for e in VoiceEmotion] else VoiceEmotion.NEUTRAL
            else:
                emotion = voice_emotion
            
            voice_profile = VoiceProfile(
                name=persona_name,
                provider=self.voice_service.tts_service.config.provider,
                emotion=emotion
            )
            
            result = self.voice_service.synthesize(text, voice_profile)
            
            return {
                "audio_data": result.audio_data,
                "text": result.text,
                "duration": result.duration,
                "format": result.format,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return {
                "audio_data": b"",
                "text": text,
                "duration": 0.0,
                "format": "wav",
                "status": "error",
                "error": str(e)
            }

class EnhancedSTTService:
    """Legacy STT service interface"""
    
    def __init__(self):
        self.stt_service = get_stt_service()
    
    async def transcribe(self, audio_data: bytes, language: str = "en") -> Dict[str, Any]:
        """Legacy transcribe method"""
        try:
            result = self.stt_service.transcribe(audio_data, language)
            return {
                "text": result.text,
                "confidence": result.confidence,
                "language": result.language,
                "duration": result.duration,
                "processing_time": result.processing_time,
                "success": True
            }
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "language": language,
                "duration": 0.0,
                "processing_time": 0.0,
                "success": False,
                "error": str(e)
            }

class EnhancedTTSService:
    """Legacy TTS service interface"""
    
    def __init__(self):
        self.tts_service = get_tts_service()
    
    async def synthesize(self, text: str, persona_name: str = "default") -> Dict[str, Any]:
        """Legacy synthesize method"""
        try:
            voice_profile = VoiceProfile(
                name=persona_name,
                provider=self.tts_service.config.provider
            )
            
            result = self.tts_service.synthesize(text, voice_profile)
            
            return {
                "audio_data": result.audio_data,
                "text": result.text,
                "duration": result.duration,
                "processing_time": result.processing_time,
                "success": True
            }
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {
                "audio_data": b"",
                "text": text,
                "duration": 0.0,
                "processing_time": 0.0,
                "success": False,
                "error": str(e)
            }

# Legacy configuration class
class VoiceConfig:
    """Legacy configuration compatibility"""
    CACHE_TTL_HOURS = 24
    DEFAULT_SAMPLE_RATE = 22050
    DEFAULT_FORMAT = "wav"