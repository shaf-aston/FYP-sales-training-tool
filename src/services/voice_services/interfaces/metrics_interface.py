"""
Metrics Collection and Error Handling Interfaces

Defines contracts for metrics collection and error handling following the Observer
and Strategy patterns respectively.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import time
import traceback


class EventType(Enum):
    """Types of service events for metrics collection"""
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    OPERATION_STARTED = "operation_started"
    OPERATION_COMPLETED = "operation_completed"
    OPERATION_FAILED = "operation_failed"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    MODEL_LOADED = "model_loaded"
    RESOURCE_USAGE = "resource_usage"
    ERROR_OCCURRED = "error_occurred"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ServiceEvent:
    """
    Service event for metrics collection
    
    Attributes:
        event_type: Type of event
        service_type: Service that generated the event
        timestamp: When the event occurred
        duration: Event duration in seconds (for completed operations)
        metadata: Additional event-specific data
        success: Whether operation was successful
        error_message: Error description if failed
    """
    event_type: EventType
    service_type: str
    timestamp: float
    duration: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class PerformanceMetrics:
    """
    Performance metrics for a service
    
    Attributes:
        total_operations: Total number of operations
        successful_operations: Number of successful operations
        failed_operations: Number of failed operations
        total_processing_time: Total time spent processing
        average_processing_time: Average processing time per operation
        min_processing_time: Minimum processing time
        max_processing_time: Maximum processing time
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        errors_by_type: Error counts by type
        last_updated: When metrics were last updated
    """
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    min_processing_time: float = float('inf')
    max_processing_time: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    errors_by_type: Optional[Dict[str, int]] = None
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.errors_by_type is None:
            self.errors_by_type = {}
        self.last_updated = time.time()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        return (self.successful_operations / max(self.total_operations, 1)) * 100
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total_cache_ops = self.cache_hits + self.cache_misses
        return (self.cache_hits / max(total_cache_ops, 1)) * 100
    
    def update_processing_time(self, duration: float) -> None:
        """Update processing time statistics"""
        self.total_processing_time += duration
        self.average_processing_time = self.total_processing_time / max(self.total_operations, 1)
        self.min_processing_time = min(self.min_processing_time, duration)
        self.max_processing_time = max(self.max_processing_time, duration)
        self.last_updated = time.time()
    
    def increment_error(self, error_type: str) -> None:
        """Increment error count for a specific type"""
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        self.last_updated = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'total_operations': self.total_operations,
            'successful_operations': self.successful_operations,
            'failed_operations': self.failed_operations,
            'success_rate': round(self.success_rate, 2),
            'total_processing_time': round(self.total_processing_time, 3),
            'average_processing_time': round(self.average_processing_time, 3),
            'min_processing_time': round(self.min_processing_time, 3) if self.min_processing_time != float('inf') else 0,
            'max_processing_time': round(self.max_processing_time, 3),
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': round(self.cache_hit_rate, 2),
            'errors_by_type': self.errors_by_type,
            'last_updated': self.last_updated
        }


class MetricsObserver(ABC):
    """
    Abstract observer for service events (Observer pattern)
    
    Observers can collect metrics, log events, or trigger alerts
    based on service events.
    """
    
    @abstractmethod
    def on_event(self, event: ServiceEvent) -> None:
        """
        Handle a service event
        
        Args:
            event: Service event to process
        """
        pass
    
    @abstractmethod
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get collected metrics
        
        Returns:
            Dictionary of metrics
        """
        pass
    
    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset all collected metrics"""
        pass


class MetricsCollector(ABC):
    """
    Abstract metrics collector (Subject in Observer pattern)
    
    Manages observers and publishes events to them.
    """
    
    def __init__(self):
        self._observers: List[MetricsObserver] = []
    
    def add_observer(self, observer: MetricsObserver) -> None:
        """
        Add an observer
        
        Args:
            observer: Observer to add
        """
        if observer not in self._observers:
            self._observers.append(observer)
    
    def remove_observer(self, observer: MetricsObserver) -> None:
        """
        Remove an observer
        
        Args:
            observer: Observer to remove
        """
        if observer in self._observers:
            self._observers.remove(observer)
    
    def notify_observers(self, event: ServiceEvent) -> None:
        """
        Notify all observers of an event
        
        Args:
            event: Event to publish
        """
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception as e:
                # Don't let observer errors break the service
                self._handle_observer_error(observer, e)
    
    def _handle_observer_error(self, observer: MetricsObserver, error: Exception) -> None:
        """Handle errors from observers"""
        # Default implementation - can be overridden
        print(f"Observer {type(observer).__name__} error: {error}")
    
    @abstractmethod
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all observers
        
        Returns:
            Aggregated metrics
        """
        pass


# Error Handling Interfaces

@dataclass
class ErrorContext:
    """
    Context information for error handling
    
    Attributes:
        error: The exception that occurred
        service_type: Service where error occurred
        operation: Operation being performed
        input_data: Input data that caused the error (may be sanitized)
        severity: Error severity level
        timestamp: When error occurred
        stack_trace: Stack trace string
        retry_count: Number of retries attempted
        metadata: Additional context information
    """
    error: Exception
    service_type: str
    operation: str
    input_data: Optional[Any] = None
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    timestamp: float = 0.0
    stack_trace: str = ""
    retry_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if not self.stack_trace:
            self.stack_trace = traceback.format_exc()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class HandlingResult:
    """
    Result of error handling
    
    Attributes:
        should_retry: Whether operation should be retried
        should_fallback: Whether to use fallback mechanism
        fallback_value: Value to return if using fallback
        delay_seconds: Delay before retry (if applicable)
        error_response: User-facing error response
        log_message: Message for logging
        notify_admin: Whether to notify administrators
    """
    should_retry: bool = False
    should_fallback: bool = False
    fallback_value: Optional[Any] = None
    delay_seconds: float = 0.0
    error_response: Optional[Dict[str, Any]] = None
    log_message: str = ""
    notify_admin: bool = False


class ErrorStrategy(ABC):
    """
    Abstract error handling strategy (Strategy pattern)
    
    Different strategies can handle different types of errors
    with appropriate responses (retry, fallback, fail-fast, etc.).
    """
    
    @abstractmethod
    def can_handle(self, error_context: ErrorContext) -> bool:
        """
        Check if this strategy can handle the error
        
        Args:
            error_context: Error context information
            
        Returns:
            True if strategy can handle this error
        """
        pass
    
    @abstractmethod
    def handle(self, error_context: ErrorContext) -> HandlingResult:
        """
        Handle the error
        
        Args:
            error_context: Error context information
            
        Returns:
            Result indicating how to proceed
        """
        pass
    
    @abstractmethod
    def get_priority(self) -> int:
        """
        Get strategy priority (lower numbers = higher priority)
        
        Returns:
            Priority number
        """
        pass


class ErrorHandler:
    """
    Error handler that manages multiple strategies
    
    Implements the Strategy pattern with automatic strategy selection
    based on error type and context.
    """
    
    def __init__(self):
        self._strategies: List[ErrorStrategy] = []
        self._fallback_strategy: Optional[ErrorStrategy] = None
    
    def add_strategy(self, strategy: ErrorStrategy) -> None:
        """
        Add an error handling strategy
        
        Args:
            strategy: Strategy to add
        """
        self._strategies.append(strategy)
        # Keep strategies sorted by priority
        self._strategies.sort(key=lambda s: s.get_priority())
    
    def set_fallback_strategy(self, strategy: ErrorStrategy) -> None:
        """
        Set fallback strategy for unhandled errors
        
        Args:
            strategy: Fallback strategy
        """
        self._fallback_strategy = strategy
    
    def handle_error(self, error_context: ErrorContext) -> HandlingResult:
        """
        Handle an error using appropriate strategy
        
        Args:
            error_context: Error context information
            
        Returns:
            Handling result
        """
        # Find first strategy that can handle the error
        for strategy in self._strategies:
            if strategy.can_handle(error_context):
                return strategy.handle(error_context)
        
        # Use fallback strategy if available
        if self._fallback_strategy:
            return self._fallback_strategy.handle(error_context)
        
        # Default handling
        return HandlingResult(
            should_retry=False,
            should_fallback=False,
            error_response={
                'error': 'Unhandled error occurred',
                'type': type(error_context.error).__name__
            },
            log_message=f"Unhandled error in {error_context.service_type}: {error_context.error}"
        )