"""Voice Services Module - Speech-to-Text, Text-to-Speech, and Audio Processing"""

from .interfaces import (
    AudioService, STTService, TTSService, CacheStrategy, MetricsObserver,
    STTConfig, TTSConfig, STTResult, TTSResult, VoiceProfile, 
    AudioFormat, QualityMetrics
)
from .factories import VoiceServiceFactory, CacheStrategyFactory, ConfigurationFactory
from .manager import VoiceServiceManager, BackwardCompatibilityAdapter, ServiceMetrics
from .metrics import MetricsCollector, RealTimeMetricsObserver, FileMetricsLogger
from .error_handling import (
    ErrorHandler, ErrorSeverity, ErrorContext, STTFallbackService, 
    TTSFallbackService, CircuitBreaker, RetryHandler, ErrorRecoveryStrategy
)
from .implementations.cache import MemoryCacheStrategy, DiskCacheStrategy
from .implementations.stt.whisper_stt_service import WhisperSTTService, SpeechRecognitionSTTService
from .implementations.tts.coqui_tts_service import CoquiTTSService, PyttsxTTSService

# Import from legacy compatibility layer
from .legacy import EnhancedVoiceService, EnhancedSTTService, EnhancedTTSService, VoiceConfig
from .legacy import get_voice_service, get_stt_service, get_tts_service
from src.models.tts.models import VoiceEmotion

# Legacy function
def get_available_services():
    return {"stt": ["whisper"], "tts": ["coqui"]}

__all__ = [
    "AudioService", "STTService", "TTSService", "CacheStrategy", "MetricsObserver",
    "STTConfig", "TTSConfig", "STTResult", "TTSResult", "VoiceProfile", 
    "AudioFormat", "QualityMetrics",
    "VoiceServiceFactory", "CacheStrategyFactory", "ConfigurationFactory",
    "VoiceServiceManager", "BackwardCompatibilityAdapter", "ServiceMetrics",
    "MetricsCollector", "RealTimeMetricsObserver", "FileMetricsLogger",
    "ErrorHandler", "ErrorSeverity", "ErrorContext", "STTFallbackService", 
    "TTSFallbackService", "CircuitBreaker", "RetryHandler", "ErrorRecoveryStrategy",
    "MemoryCacheStrategy", "DiskCacheStrategy",
    "WhisperSTTService", "SpeechRecognitionSTTService",
    "CoquiTTSService", "PyttsxTTSService",
    'EnhancedVoiceService', 'get_voice_service',
    'EnhancedSTTService', 'get_stt_service',
    'EnhancedTTSService', 'get_tts_service',
    'VoiceConfig', 'VoiceEmotion', 'get_available_services'
]