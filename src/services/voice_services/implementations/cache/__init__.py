"""
Cache Implementations Package

Provides concrete cache strategy implementations following the Strategy pattern.
Includes memory-based and disk-based caching strategies with different
performance and persistence characteristics.
"""

from .memory_cache import MemoryCacheStrategy, MemoryCacheEntry
from .disk_cache import DiskCacheStrategy, DiskCacheEntry

__all__ = [
    # Memory Cache
    'MemoryCacheStrategy',
    'MemoryCacheEntry',
    
    # Disk Cache  
    'DiskCacheStrategy',
    'DiskCacheEntry',
]