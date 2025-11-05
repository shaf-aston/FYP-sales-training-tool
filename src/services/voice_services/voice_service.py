"""
Refactored Enhanced Voice Service
Orchestrates STT and TTS services while maintaining backward compatibility
"""
import asyncio
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime

from .voice_config import VoiceEmotion, VoiceConfig, get_available_services, log_service_status

# Use existing STT/TTS services 
try:
    from .stt_service import get_stt_service, EnhancedSTTService
    STT_AVAILABLE = True
except ImportError:
    try:
        from src.infrastructure.stt_service import get_stt_service, EnhancedSTTService
        STT_AVAILABLE = True
    except ImportError:
        STT_AVAILABLE = False

try:
    from .tts_service import get_tts_service, TTSService
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

logger = logging.getLogger(__name__)

class EnhancedVoiceService:
    """
    Refactored voice service that orchestrates STT and TTS components
    Maintains backward compatibility with existing API
    """
    
    def __init__(self):
        """Initialize the voice service with STT and TTS components"""
        self.stt_service = get_stt_service() if STT_AVAILABLE else None
        self.tts_service = get_tts_service() if TTS_AVAILABLE else None
        
        # Initialize performance tracking
        self.performance_metrics = {
            'total_requests': 0,
            'stt_requests': 0,
            'tts_requests': 0,
            'errors': 0,
            'total_processing_time': 0.0
        }
        
        # Log service status
        log_service_status()
        logger.info("✅ Enhanced Voice Service initialized")
    
    async def speech_to_text(self, audio_file: Union[str, bytes], 
                           language: str = "en",
                           enable_preprocessing: bool = True,
                           enable_caching: bool = True) -> Optional[Dict]:
        """
        Convert speech to text (delegates to existing STT service)
        
        Args:
            audio_file: Path to audio file or audio bytes
            language: Language code
            enable_preprocessing: Apply text preprocessing
            enable_caching: Use result caching
            
        Returns:
            Dictionary with transcription results or None
        """
        if not self.stt_service:
            logger.warning("STT service not available")
            return None
            
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.performance_metrics['total_requests'] += 1
            self.performance_metrics['stt_requests'] += 1
            
            # Use existing STT service API
            result = self.stt_service.transcribe_audio(
                audio_file, language=language, use_cache=enable_caching
            )
            
            # Convert STTResult to expected format if needed
            if result and hasattr(result, 'text'):
                formatted_result = {
                    "text": result.text,
                    "language": result.language,
                    "confidence": result.confidence,
                    "method": "enhanced_stt_service"
                }
                if hasattr(result, 'segments'):
                    formatted_result["segments"] = result.segments
                result = formatted_result
            
            # Update metrics
            processing_time = asyncio.get_event_loop().time() - start_time
            self.performance_metrics['total_processing_time'] += processing_time
            
            return result
            
        except Exception as e:
            logger.error(f"Speech to text failed: {e}")
            self.performance_metrics['errors'] += 1
            return None
    
    async def text_to_speech(self, text: str, 
                           emotion: VoiceEmotion = VoiceEmotion.NEUTRAL,
                           speaker_voice: str = "default",
                           language: str = "en") -> Optional[bytes]:
        """
        Convert text to speech (delegates to existing TTS service)
        
        Args:
            text: Text to synthesize
            emotion: Voice emotion/style
            speaker_voice: Voice profile to use
            language: Language code
            
        Returns:
            Audio bytes or None
        """
        if not self.tts_service:
            logger.warning("TTS service not available")
            return None
            
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.performance_metrics['total_requests'] += 1
            self.performance_metrics['tts_requests'] += 1
            
            # Delegate to existing TTS service
            result = await self.tts_service.text_to_speech(
                text, emotion, speaker_voice, language
            )
            
            # Update metrics
            processing_time = asyncio.get_event_loop().time() - start_time
            self.performance_metrics['total_processing_time'] += processing_time
            
            return result
            
        except Exception as e:
            logger.error(f"Text to speech failed: {e}")
            self.performance_metrics['errors'] += 1
            return None
    
    async def batch_speech_to_text(self, audio_files: List[Union[str, bytes]],
                                  language: str = "en",
                                  enable_preprocessing: bool = True,
                                  enable_caching: bool = True) -> List[Optional[Dict]]:
        """
        Process multiple audio files in batch
        
        Args:
            audio_files: List of audio file paths or bytes
            language: Language code
            enable_preprocessing: Apply preprocessing
            enable_caching: Use caching
            
        Returns:
            List of transcription results
        """
        if not self.stt_service:
            logger.warning("STT service not available")
            return [None] * len(audio_files)
            
        try:
            # Process files individually using existing service
            results = []
            for audio_file in audio_files:
                result = await self.speech_to_text(
                    audio_file, language, enable_preprocessing, enable_caching
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Batch speech to text failed: {e}")
            self.performance_metrics['errors'] += 1
            return [None] * len(audio_files)
    
    async def generate_voice_with_context(self, text: str, context: Dict, 
                                        emotion: VoiceEmotion = VoiceEmotion.NEUTRAL) -> Optional[bytes]:
        """
        Generate voice with contextual adaptation
        
        Args:
            text: Text to synthesize
            context: Context information for adaptation
            emotion: Base emotion to use
            
        Returns:
            Audio bytes or None
        """
        try:
            # Extract speaker preference from context
            speaker_voice = context.get('preferred_voice', 'default')
            language = context.get('language', 'en')
            
            # Adapt emotion based on context
            if context.get('sentiment'):
                sentiment = context['sentiment']
                if sentiment == 'positive':
                    emotion = VoiceEmotion.HAPPY
                elif sentiment == 'negative':
                    emotion = VoiceEmotion.SAD
                elif sentiment == 'excited':
                    emotion = VoiceEmotion.EXCITED
            
            return await self.text_to_speech(text, emotion, speaker_voice, language)
            
        except Exception as e:
            logger.error(f"Context-aware voice generation failed: {e}")
            return None
    
    def get_performance_metrics(self) -> Dict:
        """
        Get combined performance metrics from all services
        
        Returns:
            Dictionary with performance statistics
        """
        # Get metrics from individual services if available
        stt_metrics = {}
        tts_metrics = {}
        
        if self.stt_service and hasattr(self.stt_service, 'get_performance_metrics'):
            try:
                stt_metrics = self.stt_service.get_performance_metrics()
            except Exception as e:
                logger.warning(f"Could not get STT metrics: {e}")
                stt_metrics = {"error": "metrics unavailable"}
        
        if self.tts_service and hasattr(self.tts_service, 'get_performance_metrics'):
            try:
                tts_metrics = self.tts_service.get_performance_metrics()
            except Exception as e:
                logger.warning(f"Could not get TTS metrics: {e}")
                tts_metrics = {"error": "metrics unavailable"}
        
        # Combine with overall metrics
        total_requests = self.performance_metrics['total_requests']
        avg_processing_time = (
            self.performance_metrics['total_processing_time'] / total_requests
            if total_requests > 0 else 0.0
        )
        
        return {
            'overall': {
                'total_requests': total_requests,
                'stt_requests': self.performance_metrics['stt_requests'],
                'tts_requests': self.performance_metrics['tts_requests'],
                'errors': self.performance_metrics['errors'],
                'avg_processing_time': f"{avg_processing_time:.2f}s",
                'uptime': datetime.now().isoformat()
            },
            'stt': stt_metrics,
            'tts': tts_metrics,
            'available_services': get_available_services()
        }
    
    def clear_cache(self) -> None:
        """Clear all service caches"""
        if self.stt_service and hasattr(self.stt_service, 'clear_cache'):
            try:
                self.stt_service.clear_cache()
                logger.info("STT cache cleared")
            except Exception as e:
                logger.warning(f"Could not clear STT cache: {e}")
        
        if self.tts_service and hasattr(self.tts_service, 'clear_cache'):
            try:
                self.tts_service.clear_cache()
                logger.info("TTS cache cleared")
            except Exception as e:
                logger.warning(f"Could not clear TTS cache: {e}")
        
        logger.info("Voice service cache clearing complete")
    
    def get_status(self) -> Dict:
        """Get service status information"""
        return {
            'status': 'active',
            'services': get_available_services(),
            'metrics': self.get_performance_metrics(),
            'config': {
                'max_cache_size': VoiceConfig.MAX_CACHE_SIZE,
                'cache_ttl_hours': VoiceConfig.CACHE_TTL_HOURS,
                'max_concurrent_requests': VoiceConfig.MAX_CONCURRENT_REQUESTS
            }
        }

# Global service instance for backward compatibility
_voice_service_instance: Optional[EnhancedVoiceService] = None

def get_voice_service() -> EnhancedVoiceService:
    """
    Get singleton voice service instance
    Maintains backward compatibility with existing code
    """
    global _voice_service_instance
    if _voice_service_instance is None:
        _voice_service_instance = EnhancedVoiceService()
    return _voice_service_instance

def reset_voice_service() -> None:
    """Reset voice service instance (for testing)"""
    global _voice_service_instance
    _voice_service_instance = None