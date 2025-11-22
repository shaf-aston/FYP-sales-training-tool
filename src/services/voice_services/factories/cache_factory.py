"""
Cache Strategy Factory

Creates cache strategy instances based on configuration and provides
cache strategy management following the Strategy pattern.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Type, Callable

from ..interfaces import CacheStrategy, CacheConfig
from ..implementations.cache import (
    MemoryCacheStrategy, 
    DiskCacheStrategy,
    # HybridCacheStrategy,  # Will implement later
    # RedisCacheStrategy,   # Will implement later
)

logger = logging.getLogger(__name__)


class CacheStrategyNotFoundError(Exception):
    """Raised when requested cache strategy is not available"""
    pass


class CacheStrategyRegistry:
    """
    Registry for cache strategy implementations
    
    Allows registration of cache strategies and provides strategy discovery.
    """
    
    def __init__(self):
        self._strategies: Dict[str, Type[CacheStrategy]] = {}
        self._factories: Dict[str, Callable[[CacheConfig], CacheStrategy]] = {}
        
        # Register built-in strategies
        self._register_builtin_strategies()
    
    def _register_builtin_strategies(self):
        """Register built-in cache strategies"""
        self.register_strategy("memory", MemoryCacheStrategy)
        self.register_strategy("disk", DiskCacheStrategy)
        
        logger.debug("Built-in cache strategies registered")
    
    def register_strategy(self, name: str, strategy_class: Type[CacheStrategy]):
        """
        Register a cache strategy class
        
        Args:
            name: Strategy name
            strategy_class: Strategy class
        """
        self._strategies[name] = strategy_class
        logger.debug(f"Registered cache strategy: {name}")
    
    def register_factory(self, name: str, factory_func: Callable[[CacheConfig], CacheStrategy]):
        """
        Register a cache strategy factory function
        
        Args:
            name: Strategy name
            factory_func: Factory function that takes CacheConfig and returns CacheStrategy
        """
        self._factories[name] = factory_func
        logger.debug(f"Registered cache strategy factory: {name}")
    
    def get_strategy_class(self, name: str) -> Type[CacheStrategy]:
        """
        Get strategy class by name
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy class
            
        Raises:
            CacheStrategyNotFoundError: If strategy not found
        """
        if name not in self._strategies:
            raise CacheStrategyNotFoundError(f"Cache strategy '{name}' not found")
        
        return self._strategies[name]
    
    def get_factory(self, name: str) -> Optional[Callable[[CacheConfig], CacheStrategy]]:
        """
        Get factory function by name
        
        Args:
            name: Strategy name
            
        Returns:
            Factory function or None if not found
        """
        return self._factories.get(name)
    
    def list_strategies(self) -> Dict[str, str]:
        """
        List available strategies
        
        Returns:
            Dictionary mapping strategy names to class names
        """
        strategies = {}
        
        for name, strategy_class in self._strategies.items():
            strategies[name] = strategy_class.__name__
        
        for name in self._factories:
            if name not in strategies:
                strategies[name] = f"Factory: {name}"
        
        return strategies
    
    def is_strategy_available(self, name: str) -> bool:
        """
        Check if strategy is available
        
        Args:
            name: Strategy name
            
        Returns:
            True if strategy is available
        """
        return name in self._strategies or name in self._factories


class CacheStrategyFactory:
    """
    Factory for creating cache strategy instances
    
    Provides centralized creation of cache strategies based on configuration
    and manages strategy lifecycle.
    """
    
    def __init__(self):
        """Initialize cache strategy factory"""
        self.registry = CacheStrategyRegistry()
        self._active_strategies: Dict[str, CacheStrategy] = {}
        
        logger.info("Cache strategy factory initialized")
    
    def create_cache_strategy(self, config: CacheConfig) -> CacheStrategy:
        """
        Create cache strategy instance
        
        Args:
            config: Cache configuration
            
        Returns:
            CacheStrategy instance
            
        Raises:
            CacheStrategyNotFoundError: If strategy not found
            ValueError: If configuration is invalid
        """
        strategy_name = config.strategy_name
        
        if not config.enabled:
            logger.info("Cache disabled - creating null cache strategy")
            return NullCacheStrategy(config)
        
        # Check if strategy is available
        if not self.registry.is_strategy_available(strategy_name):
            available = list(self.registry.list_strategies().keys())
            raise CacheStrategyNotFoundError(
                f"Cache strategy '{strategy_name}' not available. "
                f"Available strategies: {available}"
            )
        
        try:
            # Try factory function first
            factory_func = self.registry.get_factory(strategy_name)
            if factory_func:
                strategy = factory_func(config)
                logger.info(f"Created cache strategy '{strategy_name}' using factory")
                return strategy
            
            # Use strategy class
            strategy_class = self.registry.get_strategy_class(strategy_name)
            strategy = strategy_class(config)
            
            logger.info(f"Created cache strategy '{strategy_name}' using class: {strategy_class.__name__}")
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to create cache strategy '{strategy_name}': {e}")
            raise ValueError(f"Failed to create cache strategy: {e}") from e
    
    def create_memory_cache(self, config: CacheConfig) -> MemoryCacheStrategy:
        """
        Create memory cache strategy
        
        Args:
            config: Cache configuration
            
        Returns:
            MemoryCacheStrategy instance
        """
        # Override strategy name to ensure memory cache
        memory_config = CacheConfig(
            strategy_name="memory",
            enabled=config.enabled,
            ttl_hours=config.ttl_hours,
            max_size_mb=config.max_size_mb,
            eviction_policy=config.eviction_policy,
            strategy_config=config.strategy_config
        )
        
        return MemoryCacheStrategy(memory_config)
    
    def create_disk_cache(self, config: CacheConfig, 
                         cache_directory: Optional[Path] = None) -> DiskCacheStrategy:
        """
        Create disk cache strategy
        
        Args:
            config: Cache configuration
            cache_directory: Custom cache directory
            
        Returns:
            DiskCacheStrategy instance
        """
        # Prepare disk-specific configuration
        strategy_config = config.strategy_config.copy() if config.strategy_config else {}
        
        if cache_directory:
            strategy_config["cache_directory"] = str(cache_directory)
        
        disk_config = CacheConfig(
            strategy_name="disk",
            enabled=config.enabled,
            ttl_hours=config.ttl_hours,
            max_size_mb=config.max_size_mb,
            eviction_policy=config.eviction_policy,
            strategy_config=strategy_config
        )
        
        return DiskCacheStrategy(disk_config)
    
    def create_hybrid_cache(self, config: CacheConfig) -> CacheStrategy:
        """
        Create hybrid cache strategy (memory + disk)
        
        Args:
            config: Cache configuration
            
        Returns:
            HybridCacheStrategy instance
        """
        # TODO: Implement hybrid cache strategy
        logger.warning("Hybrid cache strategy not yet implemented, falling back to memory cache")
        return self.create_memory_cache(config)
    
    def create_redis_cache(self, config: CacheConfig) -> CacheStrategy:
        """
        Create Redis cache strategy
        
        Args:
            config: Cache configuration
            
        Returns:
            RedisCacheStrategy instance
        """
        # TODO: Implement Redis cache strategy
        logger.warning("Redis cache strategy not yet implemented, falling back to memory cache")
        return self.create_memory_cache(config)
    
    def create_null_cache(self, config: CacheConfig) -> 'NullCacheStrategy':
        """
        Create null cache strategy (no caching)
        
        Args:
            config: Cache configuration
            
        Returns:
            NullCacheStrategy instance
        """
        return NullCacheStrategy(config)
    
    def get_or_create_strategy(self, config: CacheConfig, 
                              instance_key: str = None) -> CacheStrategy:
        """
        Get existing strategy or create new one
        
        Args:
            config: Cache configuration
            instance_key: Key for instance caching (uses strategy_name if None)
            
        Returns:
            CacheStrategy instance
        """
        key = instance_key or config.strategy_name
        
        if key in self._active_strategies:
            logger.debug(f"Returning existing cache strategy: {key}")
            return self._active_strategies[key]
        
        strategy = self.create_cache_strategy(config)
        self._active_strategies[key] = strategy
        
        logger.debug(f"Created and cached strategy: {key}")
        return strategy
    
    def register_custom_strategy(self, name: str, strategy_class: Type[CacheStrategy]):
        """
        Register custom cache strategy
        
        Args:
            name: Strategy name
            strategy_class: Strategy class
        """
        self.registry.register_strategy(name, strategy_class)
        logger.info(f"Registered custom cache strategy: {name}")
    
    def register_custom_factory(self, name: str, 
                               factory_func: Callable[[CacheConfig], CacheStrategy]):
        """
        Register custom cache strategy factory
        
        Args:
            name: Strategy name
            factory_func: Factory function
        """
        self.registry.register_factory(name, factory_func)
        logger.info(f"Registered custom cache strategy factory: {name}")
    
    def list_available_strategies(self) -> Dict[str, str]:
        """
        List available cache strategies
        
        Returns:
            Dictionary mapping strategy names to descriptions
        """
        return self.registry.list_strategies()
    
    def validate_strategy_config(self, config: CacheConfig) -> List[str]:
        """
        Validate cache strategy configuration
        
        Args:
            config: Cache configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Basic validation
        if not config.strategy_name:
            errors.append("Strategy name is required")
        elif not self.registry.is_strategy_available(config.strategy_name):
            available = list(self.registry.list_strategies().keys())
            errors.append(
                f"Strategy '{config.strategy_name}' not available. "
                f"Available: {available}"
            )
        
        if config.max_size_mb <= 0:
            errors.append("max_size_mb must be positive")
        
        if config.ttl_hours <= 0:
            errors.append("ttl_hours must be positive")
        
        # Strategy-specific validation
        if config.strategy_name == "disk":
            strategy_config = config.strategy_config or {}
            cache_dir = strategy_config.get("cache_directory")
            
            if cache_dir:
                try:
                    path = Path(cache_dir)
                    if path.exists() and not path.is_dir():
                        errors.append(f"Cache directory path exists but is not a directory: {cache_dir}")
                except Exception as e:
                    errors.append(f"Invalid cache directory path: {e}")
        
        elif config.strategy_name == "redis":
            strategy_config = config.strategy_config or {}
            
            if "host" not in strategy_config:
                errors.append("Redis strategy requires 'host' in strategy_config")
            
            if "port" in strategy_config:
                port = strategy_config["port"]
                if not isinstance(port, int) or port <= 0 or port > 65535:
                    errors.append("Redis port must be a valid integer between 1-65535")
        
        return errors
    
    def cleanup_strategies(self):
        """Cleanup active strategies and free resources"""
        for key, strategy in self._active_strategies.items():
            try:
                if hasattr(strategy, 'cleanup'):
                    strategy.cleanup()
                logger.debug(f"Cleaned up cache strategy: {key}")
            except Exception as e:
                logger.error(f"Error cleaning up cache strategy {key}: {e}")
        
        self._active_strategies.clear()
        logger.info("Cache strategies cleaned up")


class NullCacheStrategy(CacheStrategy):
    """
    Null cache strategy that performs no caching
    
    Used when caching is disabled or as a fallback.
    """
    
    def __init__(self, config: CacheConfig):
        """Initialize null cache strategy"""
        super().__init__(config)
        logger.info("Null cache strategy initialized (caching disabled)")
    
    def get(self, key: str) -> Optional[bytes]:
        """Always returns None (cache miss)"""
        return None
    
    def put(self, key: str, value: bytes, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Always returns False (no caching)"""
        return False
    
    def delete(self, key: str) -> bool:
        """Always returns False (nothing to delete)"""
        return False
    
    def clear(self) -> None:
        """No-op for null cache"""
        pass
    
    def exists(self, key: str) -> bool:
        """Always returns False"""
        return False
    
    def cleanup_expired(self) -> int:
        """Always returns 0 (nothing to clean up)"""
        return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Return empty statistics"""
        from ..interfaces import CacheStatistics
        return CacheStatistics(
            total_entries=0,
            total_size_bytes=0,
            hit_rate=0.0,
            total_hits=0,
            total_misses=0,
            total_puts=0,
            total_deletes=0,
            cleanup_count=0,
            last_cleanup=0.0
        ).to_dict()
    
    def is_healthy(self) -> bool:
        """Always returns True"""
        return True


# Global cache factory instance
_cache_factory: Optional[CacheStrategyFactory] = None


def get_cache_factory() -> CacheStrategyFactory:
    """
    Get singleton cache factory instance
    
    Returns:
        CacheStrategyFactory instance
    """
    global _cache_factory
    
    if _cache_factory is None:
        _cache_factory = CacheStrategyFactory()
    
    return _cache_factory


def reset_cache_factory():
    """Reset cache factory (for testing)"""
    global _cache_factory
    
    if _cache_factory:
        _cache_factory.cleanup_strategies()
    
    _cache_factory = None