"""
Disk Cache Strategy Implementation

File-based cache with persistent storage and compression support.
Provides cache persistence across application restarts but with slower access times.
"""

import os
import time
import json
import hashlib
import threading
import gzip
import pickle
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from datetime import datetime

from ...interfaces import CacheStrategy, CacheConfig, CacheStatistics

logger = logging.getLogger(__name__)


class DiskCacheEntry:
    """
    Disk cache entry metadata
    
    Attributes:
        key: Cache key
        file_path: Path to cached file
        created_time: When entry was created
        last_accessed: When entry was last accessed
        access_count: Number of times accessed
        size_bytes: Size of cached data
        metadata: Additional metadata
        compressed: Whether data is compressed
    """
    
    def __init__(self, key: str, file_path: Path, size_bytes: int,
                 metadata: Optional[Dict[str, Any]] = None, compressed: bool = False):
        self.key = key
        self.file_path = file_path
        self.created_time = time.time()
        self.last_accessed = time.time()
        self.access_count = 1
        self.size_bytes = size_bytes
        self.metadata = metadata or {}
        self.compressed = compressed
    
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
    
    def exists_on_disk(self) -> bool:
        """Check if file exists on disk"""
        return self.file_path.exists()
    
    def get_file_size(self) -> int:
        """Get actual file size on disk"""
        try:
            return self.file_path.stat().st_size if self.file_path.exists() else 0
        except Exception:
            return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "key": self.key,
            "file_path": str(self.file_path),
            "created_time": self.created_time,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
            "compressed": self.compressed,
            "age_seconds": self.age_seconds(),
            "exists_on_disk": self.exists_on_disk()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DiskCacheEntry':
        """Create entry from dictionary"""
        entry = cls(
            key=data["key"],
            file_path=Path(data["file_path"]),
            size_bytes=data["size_bytes"],
            metadata=data.get("metadata", {}),
            compressed=data.get("compressed", False)
        )
        entry.created_time = data["created_time"]
        entry.last_accessed = data["last_accessed"]
        entry.access_count = data["access_count"]
        return entry


class DiskCacheStrategy(CacheStrategy):
    """
    Disk-based cache strategy with file persistence
    
    Implements a file-based cache with metadata tracking, compression support,
    and cleanup of expired/orphaned files.
    """
    
    def __init__(self, config: CacheConfig):
        """
        Initialize disk cache strategy
        
        Args:
            config: Cache configuration
        """
        super().__init__(config)
        
        # Get strategy-specific configuration
        strategy_config = config.strategy_config or {}
        
        # Determine cache directory
        cache_dir_config = strategy_config.get("cache_directory")
        if cache_dir_config:
            self.cache_dir = Path(cache_dir_config)
        else:
            from config.paths import PROJECT_ROOT
            self.cache_dir = PROJECT_ROOT / "model_cache" / "voice_cache" / "disk"
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.compress_entries = strategy_config.get("compress_entries", True)
        self.compression_level = strategy_config.get("compression_level", 6)
        self.max_size_bytes = config.max_size_mb * 1024 * 1024
        
        # Metadata file
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        
        # Cache metadata and lock
        self._entries: Dict[str, DiskCacheEntry] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = CacheStatistics()
        
        # TTL in seconds
        self._ttl_seconds = config.ttl_hours * 3600
        
        # Load existing metadata
        self._load_metadata()
        
        # Verify cache consistency
        self._verify_cache_consistency()
        
        logger.info(f"Disk cache initialized: dir={self.cache_dir}, "
                   f"compress={self.compress_entries}, max_size={config.max_size_mb}MB")
    
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
            
            entry = self._entries.get(key)
            
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
            
            # Check if file exists
            if not entry.exists_on_disk():
                self._remove_entry(key)
                self._stats.total_misses += 1
                logger.debug(f"Cache file missing: {key}")
                return None
            
            try:
                # Read file content
                value = self._read_file(entry.file_path, entry.compressed)
                
                # Update access info
                entry.touch()
                self._save_metadata()
                
                self._stats.total_hits += 1
                logger.debug(f"Cache hit: {key}")
                
                return value
                
            except Exception as e:
                logger.error(f"Error reading cache file {entry.file_path}: {e}")
                self._remove_entry(key)
                self._stats.total_misses += 1
                return None
    
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
        
        with self._lock:
            self._stats.total_puts += 1
            
            # Remove existing entry if present
            if key in self._entries:
                self._remove_entry(key)
            
            # Generate safe filename
            file_path = self._get_file_path(key)
            
            try:
                # Ensure we have space
                self._ensure_space(len(value))
                
                # Write file
                compressed_value, compressed = self._write_file(file_path, value)
                actual_size = len(compressed_value) if compressed else len(value)
                
                # Create metadata entry
                entry = DiskCacheEntry(
                    key=key,
                    file_path=file_path,
                    size_bytes=actual_size,
                    metadata=metadata,
                    compressed=compressed
                )
                
                self._entries[key] = entry
                self._save_metadata()
                
                logger.debug(f"Cached to disk: {key} ({actual_size} bytes, compressed={compressed})")
                return True
                
            except Exception as e:
                logger.error(f"Error caching to disk {key}: {e}")
                
                # Clean up partial file
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception:
                        pass
                
                return False
    
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
            
            if key in self._entries:
                self._remove_entry(key)
                logger.debug(f"Deleted from cache: {key}")
                return True
            
            return False
    
    def clear(self) -> None:
        """Clear all entries from cache"""
        with self._lock:
            # Remove all files
            for entry in self._entries.values():
                self._remove_file(entry.file_path)
            
            # Clear metadata
            self._entries.clear()
            self._save_metadata()
            self._stats.clear_count += 1
            
            logger.info("Disk cache cleared")
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and not expired
        """
        with self._lock:
            entry = self._entries.get(key)
            
            if entry is None:
                return False
            
            if entry.is_expired(self._ttl_seconds):
                self._remove_entry(key)
                return False
            
            if not entry.exists_on_disk():
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
            orphaned_keys = []
            
            for key, entry in self._entries.items():
                if entry.is_expired(self._ttl_seconds):
                    expired_keys.append(key)
                elif not entry.exists_on_disk():
                    orphaned_keys.append(key)
            
            # Remove expired and orphaned entries
            for key in expired_keys + orphaned_keys:
                self._remove_entry(key)
            
            # Clean up orphaned files (files without metadata)
            orphaned_files = self._find_orphaned_files()
            for file_path in orphaned_files:
                self._remove_file(file_path)
            
            total_cleaned = len(expired_keys) + len(orphaned_keys) + len(orphaned_files)
            
            if total_cleaned > 0:
                self._stats.cleanup_count += 1
                self._stats.last_cleanup = time.time()
                logger.debug(f"Cleaned up {len(expired_keys)} expired, "
                           f"{len(orphaned_keys)} orphaned entries, "
                           f"{len(orphaned_files)} orphaned files")
            
            return total_cleaned
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Statistics dictionary
        """
        with self._lock:
            self._stats.total_entries = len(self._entries)
            
            # Calculate total size
            total_size = sum(entry.size_bytes for entry in self._entries.values())
            self._stats.total_size_bytes = total_size
            
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
        try:
            with self._lock:
                # Check if cache directory is accessible
                if not self.cache_dir.exists():
                    logger.error(f"Cache directory does not exist: {self.cache_dir}")
                    return False
                
                # Check if we can write to cache directory
                test_file = self.cache_dir / ".health_check"
                try:
                    test_file.write_bytes(b"test")
                    test_file.unlink()
                except Exception as e:
                    logger.error(f"Cannot write to cache directory: {e}")
                    return False
                
                # Check cache consistency
                missing_files = 0
                total_entries = len(self._entries)
                
                for entry in self._entries.values():
                    if not entry.exists_on_disk():
                        missing_files += 1
                
                # Allow up to 5% missing files
                if total_entries > 0 and (missing_files / total_entries) > 0.05:
                    logger.warning(f"High number of missing files: {missing_files}/{total_entries}")
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Error checking cache health: {e}")
            return False
    
    def _get_file_path(self, key: str) -> Path:
        """Generate safe file path for cache key"""
        # Create safe filename from key hash
        key_hash = hashlib.md5(key.encode('utf-8')).hexdigest()
        
        # Create subdirectory based on first two characters for better file distribution
        subdir = key_hash[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        
        # Use hash as filename with .cache extension
        return cache_subdir / f"{key_hash}.cache"
    
    def _read_file(self, file_path: Path, compressed: bool) -> bytes:
        """Read and optionally decompress file"""
        if compressed:
            with gzip.open(file_path, 'rb') as f:
                return f.read()
        else:
            return file_path.read_bytes()
    
    def _write_file(self, file_path: Path, value: bytes) -> tuple[bytes, bool]:
        """Write and optionally compress file"""
        if self.compress_entries:
            compressed_value = gzip.compress(value, compresslevel=self.compression_level)
            
            # Only use compression if it actually reduces size significantly
            if len(compressed_value) < len(value) * 0.9:  # 10% improvement threshold
                with gzip.open(file_path, 'wb') as f:
                    f.write(value)
                return compressed_value, True
        
        # Write uncompressed
        file_path.write_bytes(value)
        return value, False
    
    def _remove_file(self, file_path: Path) -> None:
        """Safely remove file"""
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            logger.warning(f"Error removing file {file_path}: {e}")
    
    def _remove_entry(self, key: str) -> None:
        """Remove entry and associated file"""
        if key in self._entries:
            entry = self._entries.pop(key)
            self._remove_file(entry.file_path)
    
    def _load_metadata(self) -> None:
        """Load cache metadata from file"""
        if not self.metadata_file.exists():
            return
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            self._entries = {}
            for key, entry_data in metadata.get("entries", {}).items():
                try:
                    entry = DiskCacheEntry.from_dict(entry_data)
                    self._entries[key] = entry
                except Exception as e:
                    logger.warning(f"Error loading cache entry {key}: {e}")
            
            # Load statistics if available
            stats_data = metadata.get("statistics", {})
            if stats_data:
                self._stats.total_hits = stats_data.get("total_hits", 0)
                self._stats.total_misses = stats_data.get("total_misses", 0)
                self._stats.total_puts = stats_data.get("total_puts", 0)
                self._stats.total_deletes = stats_data.get("total_deletes", 0)
                self._stats.cleanup_count = stats_data.get("cleanup_count", 0)
                self._stats.clear_count = stats_data.get("clear_count", 0)
            
            logger.debug(f"Loaded {len(self._entries)} cache entries from metadata")
            
        except Exception as e:
            logger.error(f"Error loading cache metadata: {e}")
            self._entries = {}
    
    def _save_metadata(self) -> None:
        """Save cache metadata to file"""
        try:
            metadata = {
                "version": "1.0",
                "created": time.time(),
                "entries": {
                    key: entry.to_dict() for key, entry in self._entries.items()
                },
                "statistics": self._stats.to_dict()
            }
            
            # Write to temporary file first
            temp_file = self.metadata_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            # Atomic move
            temp_file.replace(self.metadata_file)
            
        except Exception as e:
            logger.error(f"Error saving cache metadata: {e}")
    
    def _verify_cache_consistency(self) -> None:
        """Verify cache consistency and fix issues"""
        inconsistent_keys = []
        
        for key, entry in self._entries.items():
            if not entry.exists_on_disk():
                inconsistent_keys.append(key)
            else:
                # Update actual file size if different
                actual_size = entry.get_file_size()
                if actual_size != entry.size_bytes:
                    logger.debug(f"Updating size for {key}: {entry.size_bytes} -> {actual_size}")
                    entry.size_bytes = actual_size
        
        # Remove inconsistent entries
        for key in inconsistent_keys:
            del self._entries[key]
        
        if inconsistent_keys:
            logger.info(f"Removed {len(inconsistent_keys)} inconsistent cache entries")
            self._save_metadata()
    
    def _find_orphaned_files(self) -> list[Path]:
        """Find cache files without metadata entries"""
        orphaned_files = []
        
        try:
            known_files = {entry.file_path for entry in self._entries.values()}
            
            # Find all .cache files in cache directory
            for cache_file in self.cache_dir.rglob("*.cache"):
                if cache_file not in known_files:
                    orphaned_files.append(cache_file)
            
        except Exception as e:
            logger.error(f"Error finding orphaned files: {e}")
        
        return orphaned_files
    
    def _ensure_space(self, required_bytes: int) -> None:
        """Ensure cache has space for new entry"""
        # Clean up expired entries first
        self.cleanup_expired()
        
        # Calculate current total size
        current_size = sum(entry.size_bytes for entry in self._entries.values())
        
        # Apply LRU eviction if still over limit
        while current_size + required_bytes > self.max_size_bytes and self._entries:
            # Find least recently used entry
            lru_key = min(self._entries.keys(), key=lambda k: self._entries[k].last_accessed)
            
            entry = self._entries[lru_key]
            current_size -= entry.size_bytes
            
            self._remove_entry(lru_key)
            logger.debug(f"Evicted LRU entry: {lru_key}")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get detailed cache information
        
        Returns:
            Detailed cache information
        """
        with self._lock:
            total_size = sum(entry.size_bytes for entry in self._entries.values())
            
            # Get directory size
            try:
                dir_size = sum(
                    f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file()
                )
            except Exception:
                dir_size = 0
            
            return {
                "strategy": "disk",
                "cache_directory": str(self.cache_dir),
                "total_entries": len(self._entries),
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "directory_size_mb": round(dir_size / 1024 / 1024, 2),
                "max_size_mb": round(self.max_size_bytes / 1024 / 1024, 2),
                "compression_enabled": self.compress_entries,
                "compression_level": self.compression_level,
                "utilization_percent": round((total_size / self.max_size_bytes) * 100, 2),
                "is_healthy": self.is_healthy(),
                "metadata_file": str(self.metadata_file),
                "orphaned_files": len(self._find_orphaned_files()),
                "statistics": self.get_statistics()
            }
    
    def optimize_cache(self) -> Dict[str, int]:
        """
        Optimize cache by cleaning up and compacting
        
        Returns:
            Optimization statistics
        """
        with self._lock:
            initial_entries = len(self._entries)
            initial_size = sum(entry.size_bytes for entry in self._entries.values())
            
            # Clean up expired and orphaned entries
            cleaned = self.cleanup_expired()
            
            # Find and remove orphaned files
            orphaned_files = self._find_orphaned_files()
            for file_path in orphaned_files:
                self._remove_file(file_path)
            
            # Verify and fix consistency
            self._verify_cache_consistency()
            
            final_entries = len(self._entries)
            final_size = sum(entry.size_bytes for entry in self._entries.values())
            
            # Save updated metadata
            self._save_metadata()
            
            optimization_stats = {
                "entries_removed": initial_entries - final_entries,
                "bytes_freed": initial_size - final_size,
                "orphaned_files_removed": len(orphaned_files),
                "cleanup_operations": cleaned,
                "final_entries": final_entries,
                "final_size_mb": round(final_size / 1024 / 1024, 2)
            }
            
            logger.info(f"Disk cache optimization completed: {optimization_stats}")
            return optimization_stats