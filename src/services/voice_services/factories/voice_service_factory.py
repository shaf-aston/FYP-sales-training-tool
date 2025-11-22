"""
Voice Service Factory

Creates voice service instances (STT and TTS) based on configuration
and manages service lifecycle following the Factory pattern.
"""

import logging
from typing import Dict, Any, Optional, Type, Callable, List
from enum import Enum

from ..interfaces import (
    STTService, TTSService, AudioService,
    STTConfig, TTSConfig, ServiceConfig
)

# Import implementations (will be created later)
from ..implementations.stt import (
    # WhisperSTTService,
    # GoogleCloudSTTService,
    # SpeechRecognitionSTTService,
)

from ..implementations.tts import (
    # CoquiTTSService,
    # PyttsxTTSService,
    # ElevenLabsTTSService,
)

from .config_factory import get_config_factory
from .cache_factory import get_cache_factory

logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Voice service types"""
    STT = "stt"
    TTS = "tts"


class VoiceServiceNotFoundError(Exception):
    """Raised when requested voice service is not available"""
    pass


class ServiceRegistry:
    """
    Registry for voice service implementations
    
    Manages available service backends and their factory functions.
    """
    
    def __init__(self):
        self._stt_services: Dict[str, Type[STTService]] = {}
        self._tts_services: Dict[str, Type[TTSService]] = {}
        self._stt_factories: Dict[str, Callable[[STTConfig], STTService]] = {}
        self._tts_factories: Dict[str, Callable[[TTSConfig], TTSService]] = {}
        
        # Register built-in services
        self._register_builtin_services()
    
    def _register_builtin_services(self):
        """Register built-in service implementations"""
        # TODO: Register actual implementations once they're created
        # self.register_stt_service("whisper", WhisperSTTService)
        # self.register_tts_service("coqui", CoquiTTSService)
        
        logger.debug("Built-in voice services registered")
    
    def register_stt_service(self, name: str, service_class: Type[STTService]):
        """
        Register STT service class
        
        Args:
            name: Service backend name
            service_class: Service class
        """
        self._stt_services[name] = service_class
        logger.debug(f"Registered STT service: {name}")
    
    def register_tts_service(self, name: str, service_class: Type[TTSService]):
        """
        Register TTS service class
        
        Args:
            name: Service backend name
            service_class: Service class
        """
        self._tts_services[name] = service_class
        logger.debug(f"Registered TTS service: {name}")
    
    def register_stt_factory(self, name: str, factory_func: Callable[[STTConfig], STTService]):
        """
        Register STT service factory function
        
        Args:
            name: Service backend name
            factory_func: Factory function
        """
        self._stt_factories[name] = factory_func
        logger.debug(f"Registered STT service factory: {name}")
    
    def register_tts_factory(self, name: str, factory_func: Callable[[TTSConfig], TTSService]):
        """
        Register TTS service factory function
        
        Args:
            name: Service backend name
            factory_func: Factory function
        """
        self._tts_factories[name] = factory_func
        logger.debug(f"Registered TTS service factory: {name}")
    
    def get_stt_service_class(self, name: str) -> Type[STTService]:
        """
        Get STT service class by name
        
        Args:
            name: Service backend name
            
        Returns:
            STT service class
            
        Raises:
            VoiceServiceNotFoundError: If service not found
        """
        if name not in self._stt_services:
            raise VoiceServiceNotFoundError(f"STT service '{name}' not found")
        
        return self._stt_services[name]
    
    def get_tts_service_class(self, name: str) -> Type[TTSService]:
        """
        Get TTS service class by name
        
        Args:
            name: Service backend name
            
        Returns:
            TTS service class
            
        Raises:
            VoiceServiceNotFoundError: If service not found
        """
        if name not in self._tts_services:
            raise VoiceServiceNotFoundError(f"TTS service '{name}' not found")
        
        return self._tts_services[name]
    
    def get_stt_factory(self, name: str) -> Optional[Callable[[STTConfig], STTService]]:
        """Get STT factory function by name"""
        return self._stt_factories.get(name)
    
    def get_tts_factory(self, name: str) -> Optional[Callable[[TTSConfig], TTSService]]:
        """Get TTS factory function by name"""
        return self._tts_factories.get(name)
    
    def list_stt_services(self) -> List[str]:
        """List available STT services"""
        services = set(self._stt_services.keys())
        services.update(self._stt_factories.keys())
        return sorted(services)
    
    def list_tts_services(self) -> List[str]:
        """List available TTS services"""
        services = set(self._tts_services.keys())
        services.update(self._tts_factories.keys())
        return sorted(services)
    
    def is_stt_service_available(self, name: str) -> bool:
        """Check if STT service is available"""
        return name in self._stt_services or name in self._stt_factories
    
    def is_tts_service_available(self, name: str) -> bool:
        """Check if TTS service is available"""
        return name in self._tts_services or name in self._tts_factories


class VoiceServiceFactory:
    """
    Factory for creating voice service instances
    
    Provides centralized creation of STT and TTS services based on configuration
    and manages service dependencies.
    """
    
    def __init__(self):
        """Initialize voice service factory"""
        self.registry = ServiceRegistry()
        self.config_factory = get_config_factory()
        self.cache_factory = get_cache_factory()
        
        self._active_services: Dict[str, AudioService] = {}
        
        logger.info("Voice service factory initialized")
    
    def create_stt_service(self, backend: str = None, 
                          config: STTConfig = None,
                          environment: str = None) -> STTService:
        """
        Create STT service instance
        
        Args:
            backend: Backend name (if None, uses config's backend)
            config: STT configuration (if None, loads from environment)
            environment: Environment name for config loading
            
        Returns:
            STTService instance
            
        Raises:
            VoiceServiceNotFoundError: If backend not available
            ValueError: If configuration is invalid
        """
        # Load configuration if not provided
        if config is None:
            config = self.config_factory.create_stt_config(backend, environment)
        
        backend_name = backend or config.backend_name
        
        # Check if service is available
        if not self.registry.is_stt_service_available(backend_name):
            available = self.registry.list_stt_services()
            raise VoiceServiceNotFoundError(
                f"STT service '{backend_name}' not available. "
                f"Available services: {available}"
            )
        
        try:
            # Create cache strategy
            cache_config = self.config_factory.create_cache_config(environment)
            cache_strategy = self.cache_factory.create_cache_strategy(cache_config)
            
            # Try factory function first
            factory_func = self.registry.get_stt_factory(backend_name)
            if factory_func:
                service = factory_func(config)
                logger.info(f"Created STT service '{backend_name}' using factory")
            else:
                # Use service class
                service_class = self.registry.get_stt_service_class(backend_name)
                service = service_class(config)
                logger.info(f"Created STT service '{backend_name}' using class: {service_class.__name__}")
            
            # Inject cache strategy if service supports it
            if hasattr(service, 'set_cache_strategy'):
                service.set_cache_strategy(cache_strategy)
                logger.debug(f"Injected cache strategy into STT service: {cache_config.strategy_name}")
            
            return service
            
        except Exception as e:
            logger.error(f"Failed to create STT service '{backend_name}': {e}")
            raise ValueError(f"Failed to create STT service: {e}") from e
    
    def create_tts_service(self, backend: str = None,
                          config: TTSConfig = None,
                          environment: str = None) -> TTSService:
        """
        Create TTS service instance
        
        Args:
            backend: Backend name (if None, uses config's backend)
            config: TTS configuration (if None, loads from environment)
            environment: Environment name for config loading
            
        Returns:
            TTSService instance
            
        Raises:
            VoiceServiceNotFoundError: If backend not available
            ValueError: If configuration is invalid
        """
        # Load configuration if not provided
        if config is None:
            config = self.config_factory.create_tts_config(backend, environment)
        
        backend_name = backend or config.backend_name
        
        # Check if service is available
        if not self.registry.is_tts_service_available(backend_name):
            available = self.registry.list_tts_services()
            raise VoiceServiceNotFoundError(
                f"TTS service '{backend_name}' not available. "
                f"Available services: {available}"
            )
        
        try:
            # Create cache strategy
            cache_config = self.config_factory.create_cache_config(environment)
            cache_strategy = self.cache_factory.create_cache_strategy(cache_config)
            
            # Load voice profiles
            voice_profiles = self.config_factory.get_voice_profiles(environment)
            
            # Try factory function first
            factory_func = self.registry.get_tts_factory(backend_name)
            if factory_func:
                service = factory_func(config)
                logger.info(f"Created TTS service '{backend_name}' using factory")
            else:
                # Use service class
                service_class = self.registry.get_tts_service_class(backend_name)
                service = service_class(config)
                logger.info(f"Created TTS service '{backend_name}' using class: {service_class.__name__}")
            
            # Inject dependencies if service supports them
            if hasattr(service, 'set_cache_strategy'):
                service.set_cache_strategy(cache_strategy)
                logger.debug(f"Injected cache strategy into TTS service: {cache_config.strategy_name}")
            
            if hasattr(service, 'set_voice_profiles'):
                service.set_voice_profiles(voice_profiles)
                logger.debug("Injected voice profiles into TTS service")
            
            return service
            
        except Exception as e:
            logger.error(f"Failed to create TTS service '{backend_name}': {e}")
            raise ValueError(f"Failed to create TTS service: {e}") from e
    
    def create_service_with_fallback(self, service_type: ServiceType,
                                   primary_backend: str = None,
                                   fallback_backends: List[str] = None,
                                   environment: str = None) -> AudioService:
        """
        Create service with fallback chain
        
        Args:
            service_type: Type of service (STT or TTS)
            primary_backend: Primary backend to try first
            fallback_backends: List of fallback backends
            environment: Environment for configuration
            
        Returns:
            AudioService instance (STT or TTS)
            
        Raises:
            VoiceServiceNotFoundError: If no backends available
        """
        # Load configuration to get fallback chain if not provided
        config_dict = self.config_factory.loader.get_voice_services_config(environment)
        service_config = config_dict.get(service_type.value, {})
        
        if primary_backend is None:
            primary_backend = service_config.get("primary_backend")
        
        if fallback_backends is None:
            fallback_backends = service_config.get("fallback_backends", [])
        
        # Try primary backend first
        backends_to_try = [primary_backend] if primary_backend else []
        backends_to_try.extend(fallback_backends or [])
        
        last_error = None
        
        for backend in backends_to_try:
            if not backend:
                continue
                
            try:
                if service_type == ServiceType.STT:
                    service = self.create_stt_service(backend, environment=environment)
                else:
                    service = self.create_tts_service(backend, environment=environment)
                
                logger.info(f"Successfully created {service_type.value.upper()} service with backend: {backend}")
                return service
                
            except Exception as e:
                logger.warning(f"Failed to create {service_type.value.upper()} service with backend '{backend}': {e}")
                last_error = e
                continue
        
        # All backends failed
        raise VoiceServiceNotFoundError(
            f"Failed to create {service_type.value.upper()} service. "
            f"Tried backends: {backends_to_try}. "
            f"Last error: {last_error}"
        )
    
    def create_audio_service(self, service_type: ServiceType,
                           backend: str = None,
                           environment: str = None) -> AudioService:
        """
        Create generic audio service (STT or TTS)
        
        Args:
            service_type: Type of service
            backend: Backend name
            environment: Environment name
            
        Returns:
            AudioService instance
        """
        if service_type == ServiceType.STT:
            return self.create_stt_service(backend, environment=environment)
        elif service_type == ServiceType.TTS:
            return self.create_tts_service(backend, environment=environment)
        else:
            raise ValueError(f"Unknown service type: {service_type}")
    
    def get_or_create_service(self, service_type: ServiceType,
                             backend: str,
                             environment: str = None,
                             instance_key: str = None) -> AudioService:
        """
        Get existing service or create new one
        
        Args:
            service_type: Type of service
            backend: Backend name
            environment: Environment name
            instance_key: Key for instance caching
            
        Returns:
            AudioService instance
        """
        key = instance_key or f"{service_type.value}_{backend}_{environment or 'default'}"
        
        if key in self._active_services:
            logger.debug(f"Returning existing service: {key}")
            return self._active_services[key]
        
        service = self.create_audio_service(service_type, backend, environment)
        self._active_services[key] = service
        
        logger.debug(f"Created and cached service: {key}")
        return service
    
    def register_custom_stt_service(self, name: str, service_class: Type[STTService]):
        """
        Register custom STT service
        
        Args:
            name: Service backend name
            service_class: Service class
        """
        self.registry.register_stt_service(name, service_class)
        logger.info(f"Registered custom STT service: {name}")
    
    def register_custom_tts_service(self, name: str, service_class: Type[TTSService]):
        """
        Register custom TTS service
        
        Args:
            name: Service backend name
            service_class: Service class
        """
        self.registry.register_tts_service(name, service_class)
        logger.info(f"Registered custom TTS service: {name}")
    
    def register_custom_stt_factory(self, name: str, 
                                   factory_func: Callable[[STTConfig], STTService]):
        """
        Register custom STT service factory
        
        Args:
            name: Service backend name
            factory_func: Factory function
        """
        self.registry.register_stt_factory(name, factory_func)
        logger.info(f"Registered custom STT service factory: {name}")
    
    def register_custom_tts_factory(self, name: str,
                                   factory_func: Callable[[TTSConfig], TTSService]):
        """
        Register custom TTS service factory
        
        Args:
            name: Service backend name
            factory_func: Factory function
        """
        self.registry.register_tts_factory(name, factory_func)
        logger.info(f"Registered custom TTS service factory: {name}")
    
    def list_available_services(self) -> Dict[str, List[str]]:
        """
        List all available services
        
        Returns:
            Dictionary with STT and TTS service lists
        """
        return {
            "stt": self.registry.list_stt_services(),
            "tts": self.registry.list_tts_services()
        }
    
    def validate_service_availability(self, service_type: ServiceType,
                                    backends: List[str]) -> Dict[str, bool]:
        """
        Validate availability of backends
        
        Args:
            service_type: Type of service
            backends: List of backend names to check
            
        Returns:
            Dictionary mapping backend names to availability
        """
        availability = {}
        
        for backend in backends:
            if service_type == ServiceType.STT:
                availability[backend] = self.registry.is_stt_service_available(backend)
            else:
                availability[backend] = self.registry.is_tts_service_available(backend)
        
        return availability
    
    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service factory information
        
        Returns:
            Service factory summary
        """
        return {
            "available_services": self.list_available_services(),
            "active_services": len(self._active_services),
            "config_environment": self.config_factory.get_environment(),
        }
    
    def cleanup_services(self):
        """Cleanup active services and free resources"""
        for key, service in self._active_services.items():
            try:
                if hasattr(service, 'cleanup'):
                    service.cleanup()
                logger.debug(f"Cleaned up service: {key}")
            except Exception as e:
                logger.error(f"Error cleaning up service {key}: {e}")
        
        self._active_services.clear()
        logger.info("Voice services cleaned up")


# Global voice service factory instance
_voice_service_factory: Optional[VoiceServiceFactory] = None


def get_voice_service_factory() -> VoiceServiceFactory:
    """
    Get singleton voice service factory instance
    
    Returns:
        VoiceServiceFactory instance
    """
    global _voice_service_factory
    
    if _voice_service_factory is None:
        _voice_service_factory = VoiceServiceFactory()
    
    return _voice_service_factory


def reset_voice_service_factory():
    """Reset voice service factory (for testing)"""
    global _voice_service_factory
    
    if _voice_service_factory:
        _voice_service_factory.cleanup_services()
    
    _voice_service_factory = None