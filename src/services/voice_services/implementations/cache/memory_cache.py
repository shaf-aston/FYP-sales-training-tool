"""
Memory Cache Strategy Implementation

In-memory cache using LRU eviction policy with configurable size limits.
Provides fast access but does not persist across application restarts.
"""

import time
import threading
from typing import Dict, Any, Optional
from collections import OrderedDict
import logging

from ...interfaces import CacheStrategy, CacheConfig, CacheStatistics

logger = logging.getLogger(__name__)


class MemoryCacheEntry:
    """
    Memory cache entry with metadata
    
    Attributes:
        value: Cached value
        created_time: When entry was created
        last_accessed: When entry was last accessed
        access_count: Number of times accessed
        metadata: Additional metadata
        size_bytes: Size of the value in bytes
    """
    
    def __init__(self, value: bytes, metadata: Optional[Dict[str, Any]] = None):
        self.value = value
        self.created_time = time.time()
        self.last_accessed = time.time()
        self.access_count = 1
        self.metadata = metadata or {}
        self.size_bytes = len(value)
    
    def touch(self):
        """Update last accessed time and increment access count"""
        self.last_accessed = time.time()
        self.access_count += 1
    
    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if entry is expired based on TTL"""
        return (time.time() - self.created_time) > ttl_seconds
    
    def age_seconds(self) -> float:
        """Get age in seconds"""
        return time.time() - self.created_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for debugging"""
        return {
            "created_time": self.created_time,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "age_seconds": self.age_seconds(),
            "metadata": self.metadata
        }


class MemoryCacheStrategy(CacheStrategy):
    """
    Memory-based cache strategy using LRU eviction
    
    Implements an in-memory cache with configurable size limits,
    TTL-based expiration, and LRU eviction policy.
    """
    
    def __init__(self, config: CacheConfig):
        """
        Initialize memory cache strategy
        
        Args:
            config: Cache configuration
        """
        super().__init__(config)
        
        # Get strategy-specific configuration
        strategy_config = config.strategy_config or {}
        self.max_entries = strategy_config.get("max_entries", 1000)
        self.memory_limit_mb = strategy_config.get("memory_limit_mb", config.max_size_mb)
        self.memory_limit_bytes = self.memory_limit_mb * 1024 * 1024
        
        # Cache storage (OrderedDict for LRU behavior)
        self._cache: OrderedDict[str, MemoryCacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Statistics
        self._total_size_bytes = 0
        self._stats = CacheStatistics()
        
        # TTL in seconds
        self._ttl_seconds = config.ttl_hours * 3600
        
        logger.info(f"Memory cache initialized: max_entries={self.max_entries}, "
                   f"memory_limit={self.memory_limit_mb}MB, ttl={config.ttl_hours}h")
    
    def get(self, key: str) -> Optional[bytes]:
        """
        Get value from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            self._stats.total_gets += 1
            
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.total_misses += 1
                logger.debug(f"Cache miss: {key}")
                return None
            
            # Check if expired
            if entry.is_expired(self._ttl_seconds):
                self._remove_entry(key)
                self._stats.total_misses += 1
                logger.debug(f"Cache expired: {key}")
                return None
            
            # Move to end (most recently used)
            entry.touch()
            self._cache.move_to_end(key)
            
            self._stats.total_hits += 1
            logger.debug(f"Cache hit: {key}")
            
            return entry.value
    
    def put(self, key: str, value: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Put value in cache
        
        Args:
            key: Cache key
            value: Value to cache
            metadata: Optional metadata
            
        Returns:
            True if successfully cached
        """
        if not value:
            logger.warning(f"Attempted to cache empty value for key: {key}")
            return False
        
        entry_size = len(value)
        
        # Check if value is too large
        if entry_size > self.memory_limit_bytes:
            logger.warning(f"Value too large to cache: {entry_size} bytes > {self.memory_limit_bytes} bytes")
            return False
        
        with self._lock:
            self._stats.total_puts += 1
            
            # Remove existing entry if present
            if key in self._cache:
                self._remove_entry(key)
            
            # Ensure we have space
            self._ensure_space(entry_size)
            
            # Create and store new entry
            entry = MemoryCacheEntry(value, metadata)
            self._cache[key] = entry
            self._total_size_bytes += entry_size
            
            logger.debug(f"Cached value: {key} ({entry_size} bytes)")
            return True
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key was deleted
        """
        with self._lock:
            self._stats.total_deletes += 1
            
            if key in self._cache:
                self._remove_entry(key)
                logger.debug(f"Deleted from cache: {key}")
                return True
            
            return False
    
    def clear(self) -> None:
        """Clear all entries from cache"""
        with self._lock:
            self._cache.clear()
            self._total_size_bytes = 0
            self._stats.clear_count += 1
            
            logger.info("Memory cache cleared")
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                return False
            
            if entry.is_expired(self._ttl_seconds):
                self._remove_entry(key)
                return False
            
            return True
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired entries
        
        Returns:
            Number of entries cleaned up
        """
        with self._lock:
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired(self._ttl_seconds):
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_entry(key)
            
            if expired_keys:
                self._stats.cleanup_count += 1
                self._stats.last_cleanup = time.time()
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")
            
            return len(expired_keys)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            self._stats.total_entries = len(self._cache)
            self._stats.total_size_bytes = self._total_size_bytes
            
            # Calculate hit rate
            total_requests = self._stats.total_hits + self._stats.total_misses
            self._stats.hit_rate = (
                self._stats.total_hits / max(total_requests, 1)
            ) * 100
            
            return self._stats.to_dict()
    
    def is_healthy(self) -> bool:
        """
        Check cache health
        
        Returns:
            True if cache is healthy
        """
        with self._lock:
            # Check for memory corruption
            calculated_size = sum(entry.size_bytes for entry in self._cache.values())
            
            if abs(calculated_size - self._total_size_bytes) > 1024:  # Allow 1KB tolerance
                logger.error(f"Cache size mismatch: calculated={calculated_size}, tracked={self._total_size_bytes}")
                return False
            
            # Check if cache is within limits
            if self._total_size_bytes > self.memory_limit_bytes:
                logger.warning(f"Cache exceeds memory limit: {self._total_size_bytes} > {self.memory_limit_bytes}")
                return False
            
            if len(self._cache) > self.max_entries:
                logger.warning(f"Cache exceeds entry limit: {len(self._cache)} > {self.max_entries}")
                return False
            
            return True
    
    def _remove_entry(self, key: str) -> None:
        """Remove entry and update size tracking"""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._total_size_bytes -= entry.size_bytes
    
    def _ensure_space(self, required_bytes: int) -> None:
        """Ensure cache has space for new entry"""
        # Remove expired entries first
        self.cleanup_expired()
        
        # Apply eviction policy if still over limits
        while (self._total_size_bytes + required_bytes > self.memory_limit_bytes or
               len(self._cache) >= self.max_entries):
            
            if not self._cache:
                break  # Cache is empty
            
            # Remove least recently used entry (first in OrderedDict)
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)
            
            logger.debug(f"Evicted LRU entry: {oldest_key}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get detailed cache information for debugging
        
        Returns:
            Detailed cache information
        """
        with self._lock:
            entries_info = []
            
            for key, entry in list(self._cache.items())[-10:]:  # Last 10 entries
                entries_info.append({
                    "key": key[:50] + "..." if len(key) > 50 else key,
                    "size_bytes": entry.size_bytes,
                    "age_seconds": entry.age_seconds(),
                    "access_count": entry.access_count,
                    "expired": entry.is_expired(self._ttl_seconds)
                })
            
            return {
                "strategy": "memory",
                "total_entries": len(self._cache),
                "total_size_mb": round(self._total_size_bytes / 1024 / 1024, 2),
                "memory_limit_mb": self.memory_limit_mb,
                "max_entries": self.max_entries,
                "ttl_hours": self._ttl_seconds / 3600,
                "utilization_percent": round(
                    (self._total_size_bytes / self.memory_limit_bytes) * 100, 2
                ),
                "entry_utilization_percent": round(
                    (len(self._cache) / self.max_entries) * 100, 2
                ),
                "is_healthy": self.is_healthy(),
                "recent_entries": entries_info,
                "statistics": self.get_statistics()
            }
    
    def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get information about specific cache entry
        
        Args:
            key: Cache key
            
        Returns:
            Entry information or None if not found
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                return None
            
            return {
                "key": key,
                "exists": True,
                "expired": entry.is_expired(self._ttl_seconds),
                **entry.to_dict()
            }
    
    def optimize_cache(self) -> Dict[str, int]:
        """
        Optimize cache by removing expired entries and defragmenting
        
        Returns:
            Optimization statistics
        """
        with self._lock:
            initial_entries = len(self._cache)
            initial_size = self._total_size_bytes
            
            # Clean up expired entries
            expired_cleaned = self.cleanup_expired()
            
            # Verify size consistency
            calculated_size = sum(entry.size_bytes for entry in self._cache.values())
            if calculated_size != self._total_size_bytes:
                logger.warning(f"Fixed size mismatch: {self._total_size_bytes} -> {calculated_size}")
                self._total_size_bytes = calculated_size
            
            final_entries = len(self._cache)
            final_size = self._total_size_bytes
            
            optimization_stats = {
                "entries_removed": initial_entries - final_entries,
                "bytes_freed": initial_size - final_size,
                "expired_entries_removed": expired_cleaned,
                "final_entries": final_entries,
                "final_size_mb": round(final_size / 1024 / 1024, 2)
            }
            
            logger.info(f"Cache optimization completed: {optimization_stats}")
            return optimization_stats