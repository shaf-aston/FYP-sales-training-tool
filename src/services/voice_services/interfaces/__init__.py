"""
Voice Services Interfaces Package

This package contains all abstract base classes and interfaces for the voice services
system, following SOLID principles and providing clear contracts for implementations.
"""

"""
Voice Services Interface Package

This package defines the contracts and abstractions for voice services,
following SOLID principles and enabling clean, testable, and maintainable code.

Key Design Patterns:
- Interface Segregation: Separate interfaces for different responsibilities
- Strategy Pattern: Pluggable implementations for services and caching
- Factory Pattern: Service creation through factories
- Observer Pattern: Event-driven metrics collection
"""

from .audio_service import (
    ServiceConfig,
    ServiceResult,
    AudioService,
)

from .stt_interface import (
    STTConfig,
    STTResult,
    ConfidenceLevel,
    LanguageCode,
    STTService,
)

from .tts_interface import (
    TTSConfig,
    TTSResult,
    VoiceProfile,
    QualityMetrics,
    AudioFormat,
    TTSService,
)

from .cache_interface import (
    CacheConfig,
    CacheStatistics,
    CacheStrategy,
)

from .metrics_interface import (
    EventType,
    ErrorSeverity,
    ServiceEvent,
    PerformanceMetrics,
    MetricsObserver,
    MetricsCollector,
    ErrorContext,
    HandlingResult,
    ErrorStrategy,
    ErrorHandler,
)

__all__ = [
    # Core service interfaces
    'AudioService',
    'ServiceConfig', 
    'ServiceResult',
    
    # STT interfaces
    'STTService', 
    'STTResult',
    'STTConfig',
    'ConfidenceLevel',
    'LanguageCode',
    
    # TTS interfaces
    'TTSService',
    'TTSResult', 
    'TTSConfig',
    'VoiceProfile',
    'QualityMetrics',
    'AudioFormat',
    
    # Infrastructure interfaces
    'CacheStrategy',
    'CacheConfig',
    'CacheStatistics',
    
    # Metrics and Error Handling
    'EventType',
    'ErrorSeverity',
    'ServiceEvent',
    'PerformanceMetrics',
    'MetricsObserver',
    'MetricsCollector',
    'ErrorContext',
    'HandlingResult',
    'ErrorStrategy',
    'ErrorHandler',
]