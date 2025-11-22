"""
Cache Strategy Interface

Defines contracts for caching implementations following the Strategy pattern.
Enables pluggable caching strategies with consistent interfaces.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import time


class CacheType(Enum):
    """Cache implementation types"""
    MEMORY = "memory"
    DISK = "disk"
    REDIS = "redis"
    HYBRID = "hybrid"


class EvictionPolicy(Enum):
    """Cache eviction policies"""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    SIZE = "size"  # Size-based eviction


@dataclass
class CacheConfig:
    """
    Configuration for cache implementations
    
    Attributes:
        cache_type: Type of cache implementation
        max_size_mb: Maximum cache size in megabytes
        ttl_hours: Time-to-live in hours
        eviction_policy: Policy for evicting items
        compression_enabled: Enable data compression
        encryption_enabled: Enable data encryption
        cleanup_interval_minutes: Interval for cleanup operations
    """
    cache_type: CacheType = CacheType.MEMORY
    max_size_mb: int = 100
    ttl_hours: int = 24
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    compression_enabled: bool = False
    encryption_enabled: bool = False
    cleanup_interval_minutes: int = 60
    
    def validate(self) -> None:
        """Validate cache configuration"""
        if self.max_size_mb <= 0:
            raise ValueError("max_size_mb must be positive")
        if self.ttl_hours <= 0:
            raise ValueError("ttl_hours must be positive")
        if self.cleanup_interval_minutes <= 0:
            raise ValueError("cleanup_interval_minutes must be positive")


@dataclass
class CacheEntry:
    """
    Cache entry with metadata
    
    Attributes:
        key: Cache key
        data: Cached data
        size_bytes: Data size in bytes
        created_at: Creation timestamp
        accessed_at: Last access timestamp
        access_count: Number of times accessed
        ttl_expires_at: TTL expiration timestamp
    """
    key: str
    data: bytes
    size_bytes: int
    created_at: float
    accessed_at: float
    access_count: int = 1
    ttl_expires_at: Optional[float] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired based on TTL"""
        if self.ttl_expires_at is None:
            return False
        return time.time() > self.ttl_expires_at
    
    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds"""
        return time.time() - self.created_at
    
    def touch(self) -> None:
        """Update access time and increment access count"""
        self.accessed_at = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """
    Cache performance statistics
    
    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        entries: Current number of entries
        size_bytes: Current cache size in bytes
        evictions: Number of evicted entries
        errors: Number of cache errors
        hit_rate: Cache hit rate percentage
        average_entry_size: Average entry size in bytes
    """
    hits: int = 0
    misses: int = 0
    entries: int = 0
    size_bytes: int = 0
    evictions: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    @property
    def average_entry_size(self) -> float:
        """Calculate average entry size"""
        return self.size_bytes / self.entries if self.entries > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'entries': self.entries,
            'size_bytes': self.size_bytes,
            'size_mb': round(self.size_bytes / 1024 / 1024, 2),
            'evictions': self.evictions,
            'errors': self.errors,
            'hit_rate': round(self.hit_rate, 2),
            'average_entry_size': round(self.average_entry_size, 2)
        }


# Alias for backward compatibility
CacheStatistics = CacheStats


class CacheStrategy(ABC):
    """
    Abstract base class for cache implementations
    
    Implements the Strategy pattern to allow pluggable caching behaviors.
    Each implementation can optimize for different use cases (speed, memory, persistence).
    """
    
    def __init__(self, config: CacheConfig):
        """
        Initialize cache with configuration
        
        Args:
            config: Cache configuration
        """
        self._config = config
        self._config.validate()
        self._stats = CacheStats()
    
    @property
    def config(self) -> CacheConfig:
        """Get cache configuration"""
        return self._config
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics"""
        return self._stats
    
    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """
        Retrieve data from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        pass
    
    @abstractmethod
    def put(self, key: str, data: bytes, ttl_hours: Optional[int] = None) -> bool:
        """
        Store data in cache
        
        Args:
            key: Cache key
            data: Data to cache
            ttl_hours: Time-to-live override
            
        Returns:
            True if successfully cached
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Remove data from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key was found and removed
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries"""
        pass
    
    @abstractmethod
    def cleanup(self) -> int:
        """
        Cleanup expired/evictable entries
        
        Returns:
            Number of entries removed
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired
        """
        pass
    
    @abstractmethod
    def keys(self) -> List[str]:
        """
        Get all cache keys
        
        Returns:
            List of cache keys
        """
        pass
    
    def get_stats(self) -> CacheStats:
        """
        Get current cache statistics
        
        Returns:
            Current statistics
        """
        return self._stats
    
    def reset_stats(self) -> None:
        """Reset cache statistics"""
        self._stats = CacheStats()
    
    def is_full(self) -> bool:
        """Check if cache is at capacity"""
        max_size_bytes = self._config.max_size_mb * 1024 * 1024
        return self._stats.size_bytes >= max_size_bytes
    
    def get_utilization(self) -> float:
        """
        Get cache utilization percentage
        
        Returns:
            Utilization percentage (0-100)
        """
        max_size_bytes = self._config.max_size_mb * 1024 * 1024
        return (self._stats.size_bytes / max_size_bytes * 100) if max_size_bytes > 0 else 0.0
    
    def _increment_hit(self) -> None:
        """Increment hit counter"""
        self._stats.hits += 1
    
    def _increment_miss(self) -> None:
        """Increment miss counter"""
        self._stats.misses += 1
    
    def _increment_error(self) -> None:
        """Increment error counter"""
        self._stats.errors += 1
    
    def _increment_eviction(self) -> None:
        """Increment eviction counter"""
        self._stats.evictions += 1
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform cache health check
        
        Returns:
            Health status information
        """
        utilization = self.get_utilization()
        
        return {
            'status': 'healthy' if utilization < 90 else 'warning' if utilization < 95 else 'critical',
            'cache_type': self._config.cache_type.value,
            'utilization_percent': round(utilization, 2),
            'stats': self._stats.to_dict(),
            'config': {
                'max_size_mb': self._config.max_size_mb,
                'ttl_hours': self._config.ttl_hours,
                'eviction_policy': self._config.eviction_policy.value
            }
        }


class CacheFactory(ABC):
    """
    Abstract factory for creating cache instances
    
    Implements the Factory pattern for cache strategy creation.
    """
    
    @abstractmethod
    def create_cache(self, cache_type: CacheType, config: CacheConfig) -> CacheStrategy:
        """
        Create a cache instance
        
        Args:
            cache_type: Type of cache to create
            config: Cache configuration
            
        Returns:
            Configured cache instance
            
        Raises:
            UnsupportedCacheTypeError: If cache type is not supported
        """
        pass
    
    @abstractmethod
    def get_supported_types(self) -> List[CacheType]:
        """
        Get supported cache types
        
        Returns:
            List of supported cache types
        """
        pass