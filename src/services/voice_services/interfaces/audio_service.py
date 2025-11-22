"""
Core Audio Service Interface

Defines the base contract for all audio processing services in the voice services system.
Implements the Interface Segregation Principle by providing focused, cohesive interfaces.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TypeVar
from dataclasses import dataclass
from enum import Enum
import time
from pathlib import Path

# Type variables for generic service implementations
T = TypeVar('T')
ConfigType = TypeVar('ConfigType', bound='ServiceConfig')
ResultType = TypeVar('ResultType', bound='ServiceResult')


class ServiceType(Enum):
    """Enumeration of available service types"""
    STT = "speech_to_text"
    TTS = "text_to_speech"
    ANALYSIS = "audio_analysis"


class ProcessingStatus(Enum):
    """Status codes for service operations"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    CACHED = "cached"
    TIMEOUT = "timeout"


@dataclass
class ServiceConfig:
    """
    Base configuration for all audio services
    
    Attributes:
        cache_enabled: Enable caching for this service
        timeout_seconds: Maximum processing time before timeout
        gpu_enabled: Use GPU acceleration if available
        debug_mode: Enable detailed logging and debugging
        max_retries: Maximum retry attempts on failure
    """
    cache_enabled: bool = True
    timeout_seconds: int = 30
    gpu_enabled: Optional[bool] = None
    debug_mode: bool = False
    max_retries: int = 3
    
    def validate(self) -> None:
        """Validate configuration parameters"""
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


@dataclass
class ServiceResult:
    """
    Base result class for all audio service operations
    
    Attributes:
        status: Processing status
        processing_time: Time taken for processing in seconds
        error_message: Error description if processing failed
        metadata: Additional service-specific metadata
        timestamp: When the operation completed
    """
    status: ProcessingStatus
    processing_time: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    timestamp: float = None
    
    def __post_init__(self):
        """Initialize computed fields"""
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def is_successful(self) -> bool:
        """Check if operation was successful"""
        return self.status in (ProcessingStatus.SUCCESS, ProcessingStatus.CACHED)
    
    @property
    def is_failed(self) -> bool:
        """Check if operation failed"""
        return self.status == ProcessingStatus.FAILED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation"""
        return {
            'status': self.status.value,
            'processing_time': self.processing_time,
            'error_message': self.error_message,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
            'is_successful': self.is_successful
        }


class AudioService(ABC):
    """
    Abstract base class for all audio processing services
    
    This interface defines the contract that all audio services must implement,
    ensuring consistent behavior across different service types (STT, TTS, Analysis).
    
    Follows the Single Responsibility Principle by focusing solely on audio processing
    operations, with separate interfaces for caching, metrics, and configuration.
    """
    
    def __init__(self, config: ConfigType):
        """
        Initialize the audio service with configuration
        
        Args:
            config: Service-specific configuration object
        """
        self._config = config
        self._config.validate()
        self._is_initialized = False
    
    @property
    def config(self) -> ConfigType:
        """Get the service configuration"""
        return self._config
    
    @property
    def service_type(self) -> ServiceType:
        """Get the type of this service"""
        return self._get_service_type()
    
    @abstractmethod
    def _get_service_type(self) -> ServiceType:
        """Return the specific service type"""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the service (load models, establish connections, etc.)
        
        This method should be called before any processing operations.
        It should be idempotent - calling it multiple times should be safe.
        
        Raises:
            ServiceInitializationError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def process(self, input_data: Any, **kwargs) -> ResultType:
        """
        Process input data and return results
        
        Args:
            input_data: Input data to process (audio bytes, text, etc.)
            **kwargs: Additional processing parameters
            
        Returns:
            Service-specific result object
            
        Raises:
            ServiceProcessingError: If processing fails
            ServiceTimeoutError: If processing exceeds timeout
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the service is available and ready for processing
        
        Returns:
            True if service is ready, False otherwise
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get service capabilities and supported features
        
        Returns:
            Dictionary describing service capabilities
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """
        Clean up resources (models, connections, temporary files)
        
        This method should be called when the service is no longer needed.
        It should be safe to call multiple times.
        """
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the service
        
        Returns:
            Dictionary with health status information
        """
        return {
            'service_type': self.service_type.value,
            'is_available': self.is_available(),
            'is_initialized': self._is_initialized,
            'config': {
                'cache_enabled': self.config.cache_enabled,
                'timeout_seconds': self.config.timeout_seconds,
                'gpu_enabled': self.config.gpu_enabled
            }
        }
    
    def validate_input(self, input_data: Any) -> None:
        """
        Validate input data before processing
        
        Args:
            input_data: Data to validate
            
        Raises:
            ValueError: If input data is invalid
        """
        if input_data is None:
            raise ValueError("Input data cannot be None")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup"""
        self.cleanup()


class ServiceFactory(ABC):
    """
    Abstract factory for creating audio services
    
    Implements the Factory pattern to decouple service creation from usage.
    """
    
    @abstractmethod
    def create_service(self, service_type: ServiceType, 
                      backend: str, config: ServiceConfig) -> AudioService:
        """
        Create a service instance
        
        Args:
            service_type: Type of service to create
            backend: Specific backend implementation
            config: Service configuration
            
        Returns:
            Configured service instance
            
        Raises:
            UnsupportedServiceError: If service type/backend combination is not supported
        """
        pass
    
    @abstractmethod
    def get_available_backends(self, service_type: ServiceType) -> list[str]:
        """
        Get available backends for a service type
        
        Args:
            service_type: Type of service
            
        Returns:
            List of available backend names
        """
        pass
    
    @abstractmethod
    def is_backend_available(self, service_type: ServiceType, backend: str) -> bool:
        """
        Check if a specific backend is available
        
        Args:
            service_type: Type of service
            backend: Backend name
            
        Returns:
            True if backend is available, False otherwise
        """
        pass