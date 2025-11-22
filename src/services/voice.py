"""
Unified Voice Service
Combines STT and TTS functionality with caching and metrics
"""
import logging
import time
from typing import Optional, List, Dict, Any, Union
import hashlib

from .stt import STTService, create_stt_service
from .tts import TTSService, create_tts_service
from src.models.stt.models import STTResult, STTConfig
from src.models.tts.models import TTSResult, TTSConfig, VoiceProfile

logger = logging.getLogger(__name__)

class VoiceCache:
    """Simple in-memory cache for voice operations"""
    
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def _generate_key(self, operation: str, data: Union[bytes, str], **kwargs) -> str:
        """Generate cache key"""
        if isinstance(data, bytes):
            data_hash = hashlib.md5(data).hexdigest()
        else:
            data_hash = hashlib.md5(data.encode()).hexdigest()
        
        params = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
        return f"{operation}:{data_hash}:{params}"
    
    def get(self, operation: str, data: Union[bytes, str], **kwargs) -> Optional[Any]:
        """Get cached result"""
        key = self._generate_key(operation, data, **kwargs)
        
        if key in self.cache:
            timestamp = self.timestamps.get(key, 0)
            if time.time() - timestamp < self.ttl:
                return self.cache[key]
            else:
                # Expired
                del self.cache[key]
                del self.timestamps[key]
        
        return None
    
    def put(self, operation: str, data: Union[bytes, str], result: Any, **kwargs):
        """Cache result"""
        key = self._generate_key(operation, data, **kwargs)
        
        # Simple LRU eviction
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
        
        self.cache[key] = result
        self.timestamps[key] = time.time()
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
        self.timestamps.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl': self.ttl
        }

class VoiceService:
    """Unified voice service combining STT and TTS"""
    
    def __init__(self, 
                 stt_service: Optional[STTService] = None,
                 tts_service: Optional[TTSService] = None,
                 enable_cache: bool = True,
                 cache_size: int = 100):
        
        self.stt_service = stt_service or create_stt_service()
        self.tts_service = tts_service or create_tts_service()
        self.cache = VoiceCache(cache_size) if enable_cache else None
        
        self.total_requests = 0
        self.cache_hits = 0
        
        logger.info("Initialized VoiceService with STT and TTS")
    
    def transcribe(self, audio_data: bytes, 
                  language: Optional[str] = None,
                  use_cache: bool = True) -> STTResult:
        """Transcribe audio to text"""
        self.total_requests += 1
        
        # Check cache
        if use_cache and self.cache:
            cached_result = self.cache.get("stt", audio_data, language=language)
            if cached_result:
                self.cache_hits += 1
                logger.debug("STT cache hit")
                return cached_result
        
        # Perform transcription
        result = self.stt_service.transcribe(audio_data, language)
        
        # Cache result
        if use_cache and self.cache:
            self.cache.put("stt", audio_data, result, language=language)
        
        return result
    
    def synthesize(self, text: str,
                  voice_profile: Optional[VoiceProfile] = None,
                  use_cache: bool = True) -> TTSResult:
        """Synthesize text to speech"""
        self.total_requests += 1
        
        # Check cache
        if use_cache and self.cache:
            profile_name = voice_profile.name if voice_profile else "default"
            cached_result = self.cache.get("tts", text, voice_profile=profile_name)
            if cached_result:
                self.cache_hits += 1
                logger.debug("TTS cache hit")
                return cached_result
        
        # Perform synthesis
        result = self.tts_service.synthesize(text, voice_profile)
        
        # Cache result
        if use_cache and self.cache:
            profile_name = voice_profile.name if voice_profile else "default"
            self.cache.put("tts", text, result, voice_profile=profile_name)
        
        return result
    
    def process_conversation(self, audio_data: bytes, 
                           response_text: str,
                           voice_profile: Optional[VoiceProfile] = None) -> Dict[str, Any]:
        """Process a complete conversation turn (STT + TTS)"""
        start_time = time.time()
        
        # Transcribe input
        stt_result = self.transcribe(audio_data)
        
        # Synthesize response
        tts_result = self.synthesize(response_text, voice_profile)
        
        processing_time = time.time() - start_time
        
        return {
            'input_text': stt_result.text,
            'input_confidence': stt_result.confidence,
            'response_text': response_text,
            'response_audio': tts_result.audio_data,
            'processing_time': processing_time,
            'stt_time': stt_result.processing_time,
            'tts_time': tts_result.processing_time
        }
    
    def batch_process(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """Process multiple operations"""
        results = []
        
        for operation in operations:
            try:
                op_type = operation.get('type')
                
                if op_type == 'stt':
                    result = self.transcribe(
                        operation['audio_data'],
                        operation.get('language')
                    )
                elif op_type == 'tts':
                    result = self.synthesize(
                        operation['text'],
                        operation.get('voice_profile')
                    )
                else:
                    raise ValueError(f"Unknown operation type: {op_type}")
                
                results.append(result)
            
            except Exception as e:
                logger.error(f"Batch operation failed: {e}")
                results.append({"error": str(e)})
        
        return results
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service metrics"""
        stt_metrics = self.stt_service.get_metrics()
        tts_metrics = self.tts_service.get_metrics()
        
        cache_hit_rate = 0.0
        if self.total_requests > 0:
            cache_hit_rate = self.cache_hits / self.total_requests
        
        return {
            'total_requests': self.total_requests,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': cache_hit_rate,
            'stt_metrics': stt_metrics,
            'tts_metrics': tts_metrics,
            'cache_stats': self.cache.get_stats() if self.cache else None
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.total_requests = 0
        self.cache_hits = 0
        self.stt_service.reset_metrics()
        self.tts_service.reset_metrics()
        if self.cache:
            self.cache.clear()
    
    def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        health = {
            'status': 'healthy',
            'stt_available': self.stt_service is not None,
            'tts_available': self.tts_service is not None,
            'cache_enabled': self.cache is not None
        }
        
        # Test STT
        try:
            test_audio = b'\x00' * 1024  # Silent audio
            self.stt_service.transcribe(test_audio)
        except Exception as e:
            health['stt_error'] = str(e)
            health['status'] = 'degraded'
        
        # Test TTS
        try:
            self.tts_service.synthesize("test")
        except Exception as e:
            health['tts_error'] = str(e)
            health['status'] = 'degraded'
        
        return health

# Factory function for easy initialization
def create_voice_service(stt_model: str = "base",
                        tts_model: str = "tts_models/en/ljspeech/tacotron2-DDC",
                        stt_provider: str = "faster_whisper",
                        tts_provider: str = "coqui",
                        enable_cache: bool = True) -> VoiceService:
    """Create a complete voice service with STT and TTS"""
    
    stt_service = create_stt_service(
        model_name=stt_model,
        provider=stt_provider
    )
    
    tts_service = create_tts_service(
        model_name=tts_model,
        provider=tts_provider
    )
    
    return VoiceService(
        stt_service=stt_service,
        tts_service=tts_service,
        enable_cache=enable_cache
    )