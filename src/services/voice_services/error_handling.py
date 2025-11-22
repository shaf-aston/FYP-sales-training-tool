import logging
import time
from typing import List, Dict, Any, Optional, Callable, Type
from dataclasses import dataclass
from threading import Lock
import traceback
from functools import wraps
from enum import Enum

from ..interfaces import STTService, TTSService, STTResult, TTSResult, AudioFormat, VoiceProfile


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    operation: str
    service_name: str
    input_data: Any
    timestamp: float
    error: Exception
    severity: ErrorSeverity
    metadata: Dict[str, Any] = None


class ErrorHandler:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._error_history: List[ErrorContext] = []
        self._lock = Lock()
        self._fallback_strategies: Dict[str, List[Callable]] = {}
        self._error_callbacks: List[Callable] = []
        self._max_history = 1000
    
    def register_fallback(self, operation: str, strategy: Callable):
        if operation not in self._fallback_strategies:
            self._fallback_strategies[operation] = []
        self._fallback_strategies[operation].append(strategy)
    
    def register_error_callback(self, callback: Callable):
        self._error_callbacks.append(callback)
    
    def handle_error(self, context: ErrorContext) -> Any:
        with self._lock:
            self._error_history.append(context)
            if len(self._error_history) > self._max_history:
                self._error_history.pop(0)
        
        self.logger.error(
            f"Error in {context.operation}: {context.error}",
            extra={
                "service": context.service_name,
                "severity": context.severity.value,
                "metadata": context.metadata
            }
        )
        
        for callback in self._error_callbacks:
            try:
                callback(context)
            except Exception as e:
                self.logger.error(f"Error callback failed: {e}")
        
        return self._execute_fallbacks(context)
    
    def _execute_fallbacks(self, context: ErrorContext) -> Any:
        fallbacks = self._fallback_strategies.get(context.operation, [])
        
        for fallback in fallbacks:
            try:
                self.logger.info(f"Attempting fallback for {context.operation}")
                return fallback(context)
            except Exception as e:
                self.logger.error(f"Fallback failed: {e}")
        
        self.logger.error(f"All fallbacks exhausted for {context.operation}")
        raise context.error
    
    def get_error_stats(self, hours: int = 24) -> Dict[str, Any]:
        cutoff_time = time.time() - (hours * 3600)
        
        with self._lock:
            recent_errors = [e for e in self._error_history if e.timestamp >= cutoff_time]
        
        if not recent_errors:
            return {"message": "No errors in the specified period"}
        
        stats = {
            "total_errors": len(recent_errors),
            "by_operation": {},
            "by_service": {},
            "by_severity": {},
            "error_rate": len(recent_errors) / hours if hours > 0 else 0
        }
        
        for error in recent_errors:
            operation = error.operation
            service = error.service_name
            severity = error.severity.value
            
            stats["by_operation"][operation] = stats["by_operation"].get(operation, 0) + 1
            stats["by_service"][service] = stats["by_service"].get(service, 0) + 1
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
        
        return stats
    
    def clear_history(self):
        with self._lock:
            self._error_history.clear()


def with_error_handling(operation: str, error_handler: ErrorHandler, 
                       service_name: str = None, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = ErrorContext(
                    operation=operation,
                    service_name=service_name or "unknown",
                    input_data={"args": args, "kwargs": kwargs},
                    timestamp=time.time(),
                    error=e,
                    severity=severity,
                    metadata={
                        "function": func.__name__,
                        "traceback": traceback.format_exc()
                    }
                )
                return error_handler.handle_error(context)
        return wrapper
    return decorator


class STTFallbackService:
    
    def __init__(self, primary_service: STTService, fallback_services: List[STTService],
                 error_handler: ErrorHandler):
        self.primary = primary_service
        self.fallbacks = fallback_services
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        
        self._setup_fallback_strategies()
    
    def _setup_fallback_strategies(self):
        def stt_fallback(context: ErrorContext) -> STTResult:
            audio_data = context.input_data.get("args", [None])[0]
            language = context.input_data.get("kwargs", {}).get("language")
            enable_timestamps = context.input_data.get("kwargs", {}).get("enable_timestamps", False)
            
            if not audio_data:
                raise ValueError("No audio data available for fallback")
            
            for i, fallback_service in enumerate(self.fallbacks):
                try:
                    self.logger.info(f"Attempting STT fallback {i + 1}/{len(self.fallbacks)}")
                    result = fallback_service.transcribe(audio_data, language, enable_timestamps)
                    result.metadata = result.metadata or {}
                    result.metadata["fallback_used"] = True
                    result.metadata["fallback_index"] = i
                    return result
                except Exception as e:
                    self.logger.error(f"STT fallback {i + 1} failed: {e}")
                    continue
            
            raise context.error
        
        self.error_handler.register_fallback("stt_transcribe", stt_fallback)
    
    @with_error_handling("stt_transcribe", None, "stt_fallback", ErrorSeverity.HIGH)
    def transcribe(self, audio_data: bytes, language: str = None, 
                  enable_timestamps: bool = False) -> STTResult:
        wrapper = with_error_handling("stt_transcribe", self.error_handler, 
                                    "primary_stt", ErrorSeverity.HIGH)
        return wrapper(self.primary.transcribe)(audio_data, language, enable_timestamps)
    
    def chunk_audio(self, audio_data: bytes, chunk_duration: float = 30.0) -> List[bytes]:
        return self.primary.chunk_audio(audio_data, chunk_duration)
    
    def validate_audio(self, audio_data: bytes) -> bool:
        return self.primary.validate_audio(audio_data)


class TTSFallbackService:
    
    def __init__(self, primary_service: TTSService, fallback_services: List[TTSService],
                 error_handler: ErrorHandler):
        self.primary = primary_service
        self.fallbacks = fallback_services
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        
        self._setup_fallback_strategies()
    
    def _setup_fallback_strategies(self):
        def tts_fallback(context: ErrorContext) -> TTSResult:
            args = context.input_data.get("args", [])
            kwargs = context.input_data.get("kwargs", {})
            
            text = args[0] if args else None
            voice_profile = kwargs.get("voice_profile")
            output_format = kwargs.get("output_format")
            
            if not text:
                raise ValueError("No text available for fallback")
            
            for i, fallback_service in enumerate(self.fallbacks):
                try:
                    self.logger.info(f"Attempting TTS fallback {i + 1}/{len(self.fallbacks)}")
                    result = fallback_service.synthesize(text, voice_profile, output_format)
                    result.metadata = result.metadata or {}
                    result.metadata["fallback_used"] = True
                    result.metadata["fallback_index"] = i
                    return result
                except Exception as e:
                    self.logger.error(f"TTS fallback {i + 1} failed: {e}")
                    continue
            
            raise context.error
        
        self.error_handler.register_fallback("tts_synthesize", tts_fallback)
    
    @with_error_handling("tts_synthesize", None, "tts_fallback", ErrorSeverity.HIGH)
    def synthesize(self, text: str, voice_profile: VoiceProfile = None,
                  output_format: AudioFormat = None) -> TTSResult:
        wrapper = with_error_handling("tts_synthesize", self.error_handler, 
                                    "primary_tts", ErrorSeverity.HIGH)
        return wrapper(self.primary.synthesize)(text, voice_profile, output_format)
    
    def chunk_text(self, text: str, max_length: int = None) -> List[str]:
        return self.primary.chunk_text(text, max_length)
    
    def get_supported_formats(self) -> List[AudioFormat]:
        return self.primary.get_supported_formats()
    
    def validate_text(self, text: str) -> bool:
        return self.primary.validate_text(text)


class CircuitBreaker:
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        self._lock = Lock()
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with self._lock:
                if self.state == "open":
                    if time.time() - self.last_failure_time >= self.recovery_timeout:
                        self.state = "half-open"
                        self.logger.info("Circuit breaker transitioning to half-open")
                    else:
                        raise Exception("Circuit breaker is open")
                
                try:
                    result = func(*args, **kwargs)
                    
                    if self.state == "half-open":
                        self.state = "closed"
                        self.failure_count = 0
                        self.logger.info("Circuit breaker closed - service recovered")
                    
                    return result
                    
                except self.expected_exception as e:
                    self.failure_count += 1
                    self.last_failure_time = time.time()
                    
                    if self.failure_count >= self.failure_threshold:
                        self.state = "open"
                        self.logger.warning(
                            f"Circuit breaker opened after {self.failure_count} failures"
                        )
                    
                    raise e
        
        return wrapper


class RetryHandler:
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, 
                 backoff_multiplier: float = 2.0, max_delay: float = 60.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_multiplier = backoff_multiplier
        self.max_delay = max_delay
        self.logger = logging.getLogger(__name__)
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(self.max_retries + 1):
                try:
                    if attempt > 0:
                        delay = min(
                            self.base_delay * (self.backoff_multiplier ** (attempt - 1)),
                            self.max_delay
                        )
                        self.logger.info(f"Retrying after {delay:.2f}s (attempt {attempt + 1})")
                        time.sleep(delay)
                    
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    else:
                        self.logger.error(f"All {self.max_retries + 1} attempts failed")
            
            raise last_exception
        
        return wrapper


class SilentFallback:
    
    @staticmethod
    def stt_silent_fallback(text: str = "Sorry, I couldn't understand the audio") -> STTResult:
        return STTResult(
            text=text,
            confidence=0.0,
            language="unknown",
            audio_duration=0.0,
            processing_time=0.001,
            metadata={"fallback": "silent", "error": True}
        )
    
    @staticmethod
    def tts_silent_fallback(text: str = "") -> TTSResult:
        silent_audio = b'\x00' * 1024
        return TTSResult(
            audio_data=silent_audio,
            text=text,
            voice_profile_name="error",
            duration=0.1,
            processing_time=0.001,
            output_format=AudioFormat.WAV,
            metadata={"fallback": "silent", "error": True}
        )


class ErrorRecoveryStrategy:
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        self.error_handler.register_fallback("stt_transcribe_silent", 
                                            lambda ctx: SilentFallback.stt_silent_fallback())
        self.error_handler.register_fallback("tts_synthesize_silent",
                                            lambda ctx: SilentFallback.tts_silent_fallback(
                                                ctx.input_data.get("args", [""])[0]
                                            ))
    
    def create_resilient_stt_service(self, services: List[STTService]) -> STTFallbackService:
        if not services:
            raise ValueError("At least one STT service required")
        
        primary = services[0]
        fallbacks = services[1:] if len(services) > 1 else []
        
        return STTFallbackService(primary, fallbacks, self.error_handler)
    
    def create_resilient_tts_service(self, services: List[TTSService]) -> TTSFallbackService:
        if not services:
            raise ValueError("At least one TTS service required")
        
        primary = services[0]
        fallbacks = services[1:] if len(services) > 1 else []
        
        return TTSFallbackService(primary, fallbacks, self.error_handler)