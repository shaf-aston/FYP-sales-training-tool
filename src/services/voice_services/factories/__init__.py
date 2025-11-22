"""
Voice Services Factory Package

Provides factory pattern implementations for creating voice service instances,
configuration management, and cache strategy creation following SOLID principles.
"""

from .config_factory import (
    ConfigurationFactory,
    ConfigurationLoader,
    ConfigurationError,
    get_config_factory,
    reset_config_factory
)

from .cache_factory import (
    CacheStrategyFactory,
    CacheStrategyRegistry,
    CacheStrategyNotFoundError,
    NullCacheStrategy,
    get_cache_factory,
    reset_cache_factory
)

from .voice_service_factory import (
    VoiceServiceFactory,
    ServiceRegistry,
    ServiceType,
    VoiceServiceNotFoundError,
    get_voice_service_factory,
    reset_voice_service_factory
)

__all__ = [
    # Configuration Factory
    'ConfigurationFactory',
    'ConfigurationLoader', 
    'ConfigurationError',
    'get_config_factory',
    'reset_config_factory',
    
    # Cache Factory
    'CacheStrategyFactory',
    'CacheStrategyRegistry',
    'CacheStrategyNotFoundError',
    'NullCacheStrategy',
    'get_cache_factory',
    'reset_cache_factory',
    
    # Voice Service Factory
    'VoiceServiceFactory',
    'ServiceRegistry',
    'ServiceType',
    'VoiceServiceNotFoundError',
    'get_voice_service_factory',
    'reset_voice_service_factory',
]