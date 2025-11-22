import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable, Union
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from contextlib import contextmanager

from ..interfaces import (
    AudioService, STTService, TTSService, CacheStrategy,
    STTConfig, TTSConfig, STTResult, TTSResult,
    VoiceProfile, AudioFormat, MetricsObserver
)
from ..factories import VoiceServiceFactory, CacheStrategyFactory
from ..implementations.cache import MemoryCacheStrategy

logger = logging.getLogger(__name__)


@dataclass
class ServiceMetrics:
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    cache_hit_rate: float = 0.0


class VoiceServiceManager:
    
    def __init__(self, factory: VoiceServiceFactory, cache_factory: CacheStrategyFactory = None):
        self.factory = factory
        self.cache_factory = cache_factory or CacheStrategyFactory()
        
        self._stt_services: Dict[str, STTService] = {}
        self._tts_services: Dict[str, TTSService] = {}
        self._cache_strategies: Dict[str, CacheStrategy] = {}
        self._metrics_observers: List[MetricsObserver] = []
        
        self._metrics = ServiceMetrics()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="voice_service")
        self._lock = threading.RLock()
        
        self._default_cache = MemoryCacheStrategy(max_size=100, ttl=3600)
        
    def register_stt_service(self, name: str, service: STTService):
        with self._lock:
            self._stt_services[name] = service
            logger.info(f"Registered STT service: {name}")
    
    def register_tts_service(self, name: str, service: TTSService):
        with self._lock:
            self._tts_services[name] = service
            logger.info(f"Registered TTS service: {name}")
    
    def register_cache_strategy(self, name: str, strategy: CacheStrategy):
        with self._lock:
            self._cache_strategies[name] = strategy
    
    def add_metrics_observer(self, observer: MetricsObserver):
        self._metrics_observers.append(observer)
    
    def get_stt_service(self, name: str = None) -> Optional[STTService]:
        with self._lock:
            if name:
                return self._stt_services.get(name)
            return next(iter(self._stt_services.values()), None)
    
    def get_tts_service(self, name: str = None) -> Optional[TTSService]:
        with self._lock:
            if name:
                return self._tts_services.get(name)
            return next(iter(self._tts_services.values()), None)
    
    def transcribe_audio(self, audio_data: bytes, service_name: str = None,
                        use_cache: bool = True, **kwargs) -> STTResult:
        return asyncio.run(self.transcribe_audio_async(
            audio_data, service_name, use_cache, **kwargs
        ))
    
    def synthesize_speech(self, text: str, service_name: str = None,
                         voice_profile: VoiceProfile = None,
                         output_format: AudioFormat = None,
                         use_cache: bool = True, **kwargs) -> TTSResult:
        return asyncio.run(self.synthesize_speech_async(
            text, service_name, voice_profile, output_format, use_cache, **kwargs
        ))
    
    async def transcribe_audio_async(self, audio_data: bytes, service_name: str = None,
                                   use_cache: bool = True, **kwargs) -> STTResult:
        service = self.get_stt_service(service_name)
        if not service:
            raise ValueError(f"STT service not found: {service_name}")
        
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key("stt", audio_data, service_name, **kwargs)
            cached_result = self._default_cache.get(cache_key)
            if cached_result:
                self._update_metrics(cache_hit=True)
                return cached_result
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                service.transcribe,
                audio_data,
                kwargs.get('language'),
                kwargs.get('enable_timestamps', False)
            )
            
            if use_cache and cache_key:
                self._default_cache.put(cache_key, result)
            
            processing_time = time.time() - start_time
            self._update_metrics(success=True, processing_time=processing_time)
            self._notify_observers("transcription_completed", result)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(error=True, processing_time=processing_time)
            self._notify_observers("transcription_error", e)
            raise
    
    async def synthesize_speech_async(self, text: str, service_name: str = None,
                                    voice_profile: VoiceProfile = None,
                                    output_format: AudioFormat = None,
                                    use_cache: bool = True, **kwargs) -> TTSResult:
        service = self.get_tts_service(service_name)
        if not service:
            raise ValueError(f"TTS service not found: {service_name}")
        
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key("tts", text, service_name,
                                               voice_profile.name if voice_profile else None,
                                               output_format, **kwargs)
            cached_result = self._default_cache.get(cache_key)
            if cached_result:
                self._update_metrics(cache_hit=True)
                return cached_result
        
        start_time = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor,
                service.synthesize,
                text,
                voice_profile,
                output_format
            )
            
            if use_cache and cache_key:
                self._default_cache.put(cache_key, result)
            
            processing_time = time.time() - start_time
            self._update_metrics(success=True, processing_time=processing_time)
            self._notify_observers("synthesis_completed", result)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._update_metrics(error=True, processing_time=processing_time)
            self._notify_observers("synthesis_error", e)
            raise
    
    def transcribe_batch(self, audio_batch: List[bytes], service_name: str = None,
                        use_cache: bool = True, **kwargs) -> List[STTResult]:
        tasks = []
        for audio_data in audio_batch:
            task = self.transcribe_audio_async(audio_data, service_name, use_cache, **kwargs)
            tasks.append(task)
        
        return asyncio.run(self._run_batch(tasks))
    
    def synthesize_batch(self, text_batch: List[str], service_name: str = None,
                        voice_profile: VoiceProfile = None,
                        output_format: AudioFormat = None,
                        use_cache: bool = True, **kwargs) -> List[TTSResult]:
        tasks = []
        for text in text_batch:
            task = self.synthesize_speech_async(
                text, service_name, voice_profile, output_format, use_cache, **kwargs
            )
            tasks.append(task)
        
        return asyncio.run(self._run_batch(tasks))
    
    async def _run_batch(self, tasks: List) -> List[Any]:
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def _generate_cache_key(self, operation: str, *args, **kwargs) -> str:
        import hashlib
        key_data = f"{operation}:{':'.join(str(arg) for arg in args)}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _update_metrics(self, success: bool = False, error: bool = False,
                       cache_hit: bool = False, processing_time: float = 0.0):
        with self._lock:
            self._metrics.request_count += 1
            
            if success:
                self._metrics.success_count += 1
            elif error:
                self._metrics.error_count += 1
            
            if processing_time > 0:
                self._metrics.total_processing_time += processing_time
                self._metrics.average_processing_time = (
                    self._metrics.total_processing_time / 
                    max(self._metrics.success_count + self._metrics.error_count, 1)
                )
            
            cache_stats = self._default_cache.get_stats()
            self._metrics.cache_hit_rate = cache_stats.get("hit_rate", 0.0)
    
    def _notify_observers(self, event: str, data: Any):
        for observer in self._metrics_observers:
            try:
                observer.on_event(event, data)
            except Exception as e:
                logger.error(f"Metrics observer error: {e}")
    
    def get_metrics(self) -> ServiceMetrics:
        with self._lock:
            return ServiceMetrics(
                request_count=self._metrics.request_count,
                success_count=self._metrics.success_count,
                error_count=self._metrics.error_count,
                total_processing_time=self._metrics.total_processing_time,
                average_processing_time=self._metrics.average_processing_time,
                cache_hit_rate=self._metrics.cache_hit_rate
            )
    
    def reset_metrics(self):
        with self._lock:
            self._metrics = ServiceMetrics()
    
    def list_services(self) -> Dict[str, List[str]]:
        with self._lock:
            return {
                "stt_services": list(self._stt_services.keys()),
                "tts_services": list(self._tts_services.keys()),
                "cache_strategies": list(self._cache_strategies.keys())
            }
    
    def health_check(self) -> Dict[str, Any]:
        health_status = {
            "status": "healthy",
            "services": {},
            "cache": {},
            "metrics": self.get_metrics().__dict__
        }
        
        for name, service in self._stt_services.items():
            try:
                health_status["services"][f"stt_{name}"] = "healthy"
            except Exception as e:
                health_status["services"][f"stt_{name}"] = f"unhealthy: {e}"
                health_status["status"] = "degraded"
        
        for name, service in self._tts_services.items():
            try:
                health_status["services"][f"tts_{name}"] = "healthy"
            except Exception as e:
                health_status["services"][f"tts_{name}"] = f"unhealthy: {e}"
                health_status["status"] = "degraded"
        
        try:
            cache_stats = self._default_cache.get_stats()
            health_status["cache"] = cache_stats
        except Exception as e:
            health_status["cache"] = f"error: {e}"
        
        return health_status
    
    @contextmanager
    def service_context(self, stt_service: str = None, tts_service: str = None):
        original_stt = getattr(self, '_current_stt', None)
        original_tts = getattr(self, '_current_tts', None)
        
        try:
            if stt_service:
                self._current_stt = stt_service
            if tts_service:
                self._current_tts = tts_service
            yield self
        finally:
            self._current_stt = original_stt
            self._current_tts = original_tts
    
    def shutdown(self):
        logger.info("Shutting down VoiceServiceManager")
        self._executor.shutdown(wait=True)
        for cache_strategy in self._cache_strategies.values():
            if hasattr(cache_strategy, 'close'):
                cache_strategy.close()


class BackwardCompatibilityAdapter:
    
    def __init__(self, manager: VoiceServiceManager):
        self.manager = manager
        self._legacy_config = {}
    
    def configure_legacy_stt(self, **config):
        self._legacy_config.update(config)
    
    def configure_legacy_tts(self, **config):
        self._legacy_config.update(config)
    
    def transcribe(self, audio_data: bytes, **kwargs) -> dict:
        try:
            result = self.manager.transcribe_audio(audio_data, **kwargs)
            return {
                "text": result.text,
                "confidence": result.confidence,
                "language": result.language,
                "processing_time": result.processing_time,
                "success": True
            }
        except Exception as e:
            return {
                "text": "",
                "confidence": 0.0,
                "language": "unknown",
                "error": str(e),
                "success": False
            }
    
    def synthesize(self, text: str, **kwargs) -> dict:
        try:
            result = self.manager.synthesize_speech(text, **kwargs)
            return {
                "audio_data": result.audio_data,
                "duration": result.duration,
                "format": result.output_format.value,
                "processing_time": result.processing_time,
                "success": True
            }
        except Exception as e:
            return {
                "audio_data": b"",
                "duration": 0.0,
                "format": "wav",
                "error": str(e),
                "success": False
            }