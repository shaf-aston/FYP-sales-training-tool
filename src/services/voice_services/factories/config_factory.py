"""
Configuration Management Factory

Provides centralized configuration loading and management for voice services,
supporting multiple environments and configuration inheritance.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
import logging
from copy import deepcopy

from ...interfaces import (
    ServiceConfig, STTConfig, TTSConfig, CacheConfig,
    AudioFormat, LanguageCode, ConfidenceLevel
)

logger = logging.getLogger(__name__)


@dataclass
class ConfigurationSource:
    """Configuration source metadata"""
    path: Path
    environment: str
    priority: int
    loaded: bool = False
    content: Optional[Dict[str, Any]] = None


class ConfigurationError(Exception):
    """Configuration-related errors"""
    pass


class ConfigurationLoader:
    """
    Configuration loader with environment inheritance and validation
    
    Supports loading configurations from multiple YAML files with inheritance,
    environment variable interpolation, and configuration validation.
    """
    
    def __init__(self, config_root: Optional[Path] = None):
        """
        Initialize configuration loader
        
        Args:
            config_root: Root directory for configuration files
        """
        if config_root is None:
            # Default to config/voice_services directory
            from config.paths import PROJECT_ROOT
            config_root = PROJECT_ROOT / "config" / "voice_services"
            
        self.config_root = Path(config_root)
        self.config_cache: Dict[str, Dict[str, Any]] = {}
        self.sources: List[ConfigurationSource] = []
        
        # Ensure config directory exists
        self.config_root.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Configuration loader initialized with root: {self.config_root}")
    
    def discover_config_files(self, environment: str = "development") -> List[ConfigurationSource]:
        """
        Discover available configuration files
        
        Args:
            environment: Target environment name
            
        Returns:
            List of configuration sources in priority order
        """
        sources = []
        
        # Base configuration (lowest priority)
        base_config = self.config_root / "base.yaml"
        if base_config.exists():
            sources.append(ConfigurationSource(
                path=base_config,
                environment="base",
                priority=1
            ))
        
        # Environment-specific configuration (highest priority)
        env_config = self.config_root / f"{environment}.yaml"
        if env_config.exists():
            sources.append(ConfigurationSource(
                path=env_config,
                environment=environment,
                priority=2
            ))
        else:
            logger.warning(f"Environment configuration not found: {env_config}")
        
        # Sort by priority
        sources.sort(key=lambda s: s.priority)
        return sources
    
    def _interpolate_variables(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interpolate environment variables in configuration
        
        Supports ${VAR_NAME} and ${VAR_NAME:-default_value} syntax
        """
        import re
        
        def interpolate_value(value):
            if isinstance(value, str):
                # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
                pattern = r'\\${([^}]+)}'
                
                def replace_var(match):
                    var_expr = match.group(1)
                    
                    # Check for default value
                    if ":-" in var_expr:
                        var_name, default_value = var_expr.split(":-", 1)
                    else:
                        var_name, default_value = var_expr, None
                    
                    # Get environment variable value
                    env_value = os.environ.get(var_name.strip())
                    
                    if env_value is not None:
                        return env_value
                    elif default_value is not None:
                        return default_value
                    else:
                        logger.warning(f"Environment variable {var_name} not found and no default provided")
                        return match.group(0)  # Return original placeholder
                
                return re.sub(pattern, replace_var, value)
            
            elif isinstance(value, dict):
                return {k: interpolate_value(v) for k, v in value.items()}
            
            elif isinstance(value, list):
                return [interpolate_value(item) for item in value]
            
            return value
        
        return interpolate_value(content)
    
    def _merge_configurations(self, sources: List[ConfigurationSource]) -> Dict[str, Any]:
        """
        Merge multiple configuration sources with inheritance
        
        Later sources override earlier ones. Supports deep merging of dictionaries.
        """
        merged_config = {}
        
        for source in sources:
            if source.content:
                self._deep_merge(merged_config, source.content)
                logger.debug(f"Merged configuration from {source.path}")
        
        return merged_config
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]):
        """
        Deep merge two dictionaries
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = deepcopy(value)
    
    def load_configuration(self, environment: str = "development", 
                         force_reload: bool = False) -> Dict[str, Any]:
        """
        Load and merge configuration for environment
        
        Args:
            environment: Environment name (development, production, testing)
            force_reload: Force reload even if cached
            
        Returns:
            Merged configuration dictionary
        """
        cache_key = environment
        
        # Return cached if available and not forcing reload
        if not force_reload and cache_key in self.config_cache:
            logger.debug(f"Using cached configuration for {environment}")
            return self.config_cache[cache_key]
        
        # Discover configuration files
        sources = self.discover_config_files(environment)
        
        # Load each configuration file
        for source in sources:
            try:
                with open(source.path, 'r', encoding='utf-8') as f:
                    source.content = yaml.safe_load(f)
                source.loaded = True
                logger.debug(f"Loaded configuration: {source.path}")
                
            except Exception as e:
                logger.error(f"Failed to load configuration {source.path}: {e}")
                raise ConfigurationError(f"Failed to load {source.path}: {e}")
        
        # Merge configurations
        merged_config = self._merge_configurations(sources)
        
        # Interpolate environment variables
        merged_config = self._interpolate_variables(merged_config)
        
        # Cache the result
        self.config_cache[cache_key] = merged_config
        self.sources = sources
        
        logger.info(f"Configuration loaded for environment: {environment}")
        return merged_config
    
    def get_voice_services_config(self, environment: str = "development") -> Dict[str, Any]:
        """
        Get voice services configuration section
        
        Args:
            environment: Environment name
            
        Returns:
            Voice services configuration
        """
        full_config = self.load_configuration(environment)
        return full_config.get("voice_services", {})
    
    def create_stt_config(self, environment: str = "development", 
                         backend: str = None) -> STTConfig:
        """
        Create STTConfig from loaded configuration
        
        Args:
            environment: Environment name
            backend: Backend name (if None, uses primary backend)
            
        Returns:
            STTConfig instance
        """
        config = self.get_voice_services_config(environment)
        stt_config = config.get("stt", {})
        
        if backend is None:
            backend = stt_config.get("primary_backend", "whisper")
        
        # Get backend-specific configuration
        backend_config = stt_config.get("backends", {}).get(backend, {})
        common_config = stt_config.get("common", {})
        
        # Merge common and backend-specific settings
        merged_config = deepcopy(common_config)
        self._deep_merge(merged_config, backend_config)
        
        return STTConfig(
            backend_name=backend,
            language=LanguageCode(merged_config.get("language", "en")),
            sample_rate=merged_config.get("sample_rate", 16000),
            confidence_threshold=merged_config.get("confidence_threshold", 0.7),
            enable_preprocessing=merged_config.get("enable_preprocessing", True),
            model_config=merged_config,
            timeout_seconds=config.get("global", {}).get("timeout_seconds", 30)
        )
    
    def create_tts_config(self, environment: str = "development",
                         backend: str = None) -> TTSConfig:
        """
        Create TTSConfig from loaded configuration
        
        Args:
            environment: Environment name
            backend: Backend name (if None, uses primary backend)
            
        Returns:
            TTSConfig instance
        """
        config = self.get_voice_services_config(environment)
        tts_config = config.get("tts", {})
        
        if backend is None:
            backend = tts_config.get("primary_backend", "coqui")
        
        # Get backend-specific configuration
        backend_config = tts_config.get("backends", {}).get(backend, {})
        common_config = tts_config.get("common", {})
        
        # Merge common and backend-specific settings
        merged_config = deepcopy(common_config)
        self._deep_merge(merged_config, backend_config)
        
        return TTSConfig(
            backend_name=backend,
            output_format=AudioFormat(merged_config.get("output_format", "wav")),
            sample_rate=merged_config.get("sample_rate", 22050),
            enable_chunking=merged_config.get("enable_chunking", True),
            max_chunk_length=merged_config.get("max_chunk_length", 500),
            model_config=merged_config,
            timeout_seconds=config.get("global", {}).get("timeout_seconds", 30)
        )
    
    def create_cache_config(self, environment: str = "development") -> CacheConfig:
        """
        Create CacheConfig from loaded configuration
        
        Args:
            environment: Environment name
            
        Returns:
            CacheConfig instance
        """
        config = self.get_voice_services_config(environment)
        cache_config = config.get("cache", {})
        
        strategy = cache_config.get("strategy", "memory")
        strategy_config = cache_config.get("strategies", {}).get(strategy, {})
        
        return CacheConfig(
            strategy_name=strategy,
            enabled=cache_config.get("enabled", True),
            ttl_hours=cache_config.get("ttl_hours", 24),
            max_size_mb=cache_config.get("max_size_mb", 500),
            eviction_policy=cache_config.get("eviction_policy", "lru"),
            strategy_config=strategy_config
        )
    
    def load_voice_profiles(self, environment: str = "development") -> Dict[str, Any]:
        """
        Load voice profiles configuration
        
        Args:
            environment: Environment name
            
        Returns:
            Voice profiles configuration
        """
        profiles_path = self.config_root / "voice_profiles.yaml"
        
        if not profiles_path.exists():
            logger.warning(f"Voice profiles configuration not found: {profiles_path}")
            return {}
        
        try:
            with open(profiles_path, 'r', encoding='utf-8') as f:
                profiles_config = yaml.safe_load(f)
            
            # Interpolate environment variables
            profiles_config = self._interpolate_variables(profiles_config)
            
            logger.info("Voice profiles configuration loaded")
            return profiles_config
        
        except Exception as e:
            logger.error(f"Failed to load voice profiles: {e}")
            raise ConfigurationError(f"Failed to load voice profiles: {e}")
    
    def load_backends_config(self, environment: str = "development") -> Dict[str, Any]:
        """
        Load backends configuration
        
        Args:
            environment: Environment name
            
        Returns:
            Backends configuration
        """
        backends_path = self.config_root / "backends.yaml"
        
        if not backends_path.exists():
            logger.warning(f"Backends configuration not found: {backends_path}")
            return {}
        
        try:
            with open(backends_path, 'r', encoding='utf-8') as f:
                backends_config = yaml.safe_load(f)
            
            # Interpolate environment variables
            backends_config = self._interpolate_variables(backends_config)
            
            logger.info("Backends configuration loaded")
            return backends_config
        
        except Exception as e:
            logger.error(f"Failed to load backends config: {e}")
            raise ConfigurationError(f"Failed to load backends config: {e}")
    
    def validate_configuration(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration structure and values
        
        Args:
            config: Configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        voice_services = config.get("voice_services", {})
        
        # Validate STT configuration
        stt_config = voice_services.get("stt", {})
        primary_backend = stt_config.get("primary_backend")
        
        if not primary_backend:
            errors.append("STT primary_backend is required")
        
        backends = stt_config.get("backends", {})
        if primary_backend and primary_backend not in backends:
            errors.append(f"STT primary backend '{primary_backend}' not defined in backends")
        
        # Validate TTS configuration
        tts_config = voice_services.get("tts", {})
        primary_backend = tts_config.get("primary_backend")
        
        if not primary_backend:
            errors.append("TTS primary_backend is required")
        
        backends = tts_config.get("backends", {})
        if primary_backend and primary_backend not in backends:
            errors.append(f"TTS primary backend '{primary_backend}' not defined in backends")
        
        # Validate cache configuration
        cache_config = voice_services.get("cache", {})
        cache_strategy = cache_config.get("strategy")
        
        if cache_strategy:
            strategies = cache_config.get("strategies", {})
            if cache_strategy not in strategies:
                errors.append(f"Cache strategy '{cache_strategy}' not defined in strategies")
        
        return errors
    
    def get_configuration_summary(self, environment: str = "development") -> Dict[str, Any]:
        """
        Get configuration summary for debugging
        
        Args:
            environment: Environment name
            
        Returns:
            Configuration summary
        """
        config = self.load_configuration(environment)
        voice_services = config.get("voice_services", {})
        
        return {
            "environment": environment,
            "config_root": str(self.config_root),
            "sources_loaded": len(self.sources),
            "stt_primary_backend": voice_services.get("stt", {}).get("primary_backend"),
            "tts_primary_backend": voice_services.get("tts", {}).get("primary_backend"),
            "cache_strategy": voice_services.get("cache", {}).get("strategy"),
            "global_settings": voice_services.get("global", {}),
            "validation_errors": self.validate_configuration(config)
        }


class ConfigurationFactory:
    """
    Factory for creating configuration instances
    
    Provides centralized access to configuration loading and creation of
    service-specific configuration objects.
    """
    
    def __init__(self, config_root: Optional[Path] = None):
        """
        Initialize configuration factory
        
        Args:
            config_root: Root directory for configuration files
        """
        self.loader = ConfigurationLoader(config_root)
        self._current_environment = "development"
        
        logger.info("Configuration factory initialized")
    
    def set_environment(self, environment: str):
        """
        Set the current environment
        
        Args:
            environment: Environment name
        """
        self._current_environment = environment
        logger.info(f"Configuration environment set to: {environment}")
    
    def get_environment(self) -> str:
        """Get current environment"""
        return self._current_environment
    
    def create_stt_config(self, backend: str = None, 
                         environment: str = None) -> STTConfig:
        """
        Create STT configuration
        
        Args:
            backend: Backend name
            environment: Environment (uses current if None)
            
        Returns:
            STTConfig instance
        """
        env = environment or self._current_environment
        return self.loader.create_stt_config(env, backend)
    
    def create_tts_config(self, backend: str = None,
                         environment: str = None) -> TTSConfig:
        """
        Create TTS configuration
        
        Args:
            backend: Backend name
            environment: Environment (uses current if None)
            
        Returns:
            TTSConfig instance
        """
        env = environment or self._current_environment
        return self.loader.create_tts_config(env, backend)
    
    def create_cache_config(self, environment: str = None) -> CacheConfig:
        """
        Create cache configuration
        
        Args:
            environment: Environment (uses current if None)
            
        Returns:
            CacheConfig instance
        """
        env = environment or self._current_environment
        return self.loader.create_cache_config(env)
    
    def get_voice_profiles(self, environment: str = None) -> Dict[str, Any]:
        """
        Get voice profiles configuration
        
        Args:
            environment: Environment (uses current if None)
            
        Returns:
            Voice profiles configuration
        """
        env = environment or self._current_environment
        return self.loader.load_voice_profiles(env)
    
    def get_backends_config(self, environment: str = None) -> Dict[str, Any]:
        """
        Get backends configuration
        
        Args:
            environment: Environment (uses current if None)
            
        Returns:
            Backends configuration
        """
        env = environment or self._current_environment
        return self.loader.load_backends_config(env)
    
    def reload_configuration(self):
        """Force reload configuration from files"""
        self.loader.config_cache.clear()
        logger.info("Configuration cache cleared - will reload on next access")
    
    def validate_current_configuration(self) -> List[str]:
        """
        Validate current environment configuration
        
        Returns:
            List of validation errors
        """
        config = self.loader.load_configuration(self._current_environment)
        return self.loader.validate_configuration(config)
    
    def get_configuration_info(self) -> Dict[str, Any]:
        """
        Get configuration information for debugging
        
        Returns:
            Configuration summary
        """
        return self.loader.get_configuration_summary(self._current_environment)


# Global configuration factory instance
_config_factory: Optional[ConfigurationFactory] = None


def get_config_factory(config_root: Optional[Path] = None) -> ConfigurationFactory:
    """
    Get singleton configuration factory instance
    
    Args:
        config_root: Root directory for configuration files
        
    Returns:
        ConfigurationFactory instance
    """
    global _config_factory
    
    if _config_factory is None:
        _config_factory = ConfigurationFactory(config_root)
    
    return _config_factory


def reset_config_factory():
    """Reset configuration factory (for testing)"""
    global _config_factory
    _config_factory = None