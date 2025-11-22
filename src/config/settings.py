"""
Centralized Configuration Management
Environment variable support and dataclass-based configs
"""
import os
import json
import logging
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Constants for backward compatibility
MAX_CONTEXT_LENGTH = 4000

# Database paths and limits
SESSIONS_DB_PATH = os.path.join("data", "sessions.db")
QUALITY_DB_PATH = os.path.join("data", "quality_metrics.db")
DEFAULT_CONVERSATION_LIMIT = 50

logger = logging.getLogger(__name__)

@dataclass
class STTConfig:
    """Speech-to-Text configuration"""
    provider: str = "faster_whisper"
    model_name: str = "base"
    device: str = "auto"
    language: Optional[str] = None
    
    # Confidence thresholds
    high_confidence: float = 0.8
    medium_confidence: float = 0.6
    low_confidence: float = 0.3
    
    # Processing options
    enable_vad: bool = True  # Voice Activity Detection
    enable_noise_reduction: bool = True
    chunk_length_s: float = 30.0

@dataclass
class TTSConfig:
    """Text-to-Speech configuration"""
    provider: str = "coqui"
    model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"
    speaker_name: Optional[str] = None
    
    # Voice settings
    speed: float = 1.0
    volume: float = 0.8
    gender: str = "female"
    
    # Quality settings
    sample_rate: int = 22050
    enable_emotion: bool = False

@dataclass
class AIConfig:
    """AI model configuration"""
    model_name: str = "microsoft/DialoGPT-medium"
    device: str = "auto"
    max_length: int = 512
    temperature: float = 0.7
    
    # Context management
    max_context_turns: int = 10
    context_window: int = 2048
    
    # Response settings
    min_response_length: int = 5
    max_response_length: int = 300
    repetition_penalty: float = 1.1

@dataclass
class DatabaseConfig:
    """Database configuration"""
    db_path: str = "data/chatbot.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 6
    
    # Connection settings
    timeout_seconds: int = 30
    max_connections: int = 10

@dataclass
class CacheConfig:
    """Cache configuration"""
    model_cache_dir: str = "model_cache"
    audio_cache_dir: str = "audio_cache"
    
    # Size limits (MB)
    max_model_cache_size: int = 1000
    max_audio_cache_size: int = 500
    
    # TTL settings (hours)
    model_cache_ttl: int = 168  # 1 week
    audio_cache_ttl: int = 24   # 1 day

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # File logging
    log_to_file: bool = True
    log_dir: str = "logs"
    log_file: str = "chatbot.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    
    # Console logging
    log_to_console: bool = True

@dataclass
class AppConfig:
    """Main application configuration"""
    # Service configs
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    
    # Application settings
    app_name: str = "Sales Roleplay Chatbot"
    version: str = "1.0.0"
    debug: bool = False
    
    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    # Security
    secret_key: str = "your-secret-key-here"
    enable_cors: bool = True

class ConfigManager:
    """Configuration manager with environment variable support"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or "config/app_config.json"
        self.config = AppConfig()
        self._load_config()
        self._apply_env_overrides()
    
    def _load_config(self):
        """Load configuration from file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Update config with loaded data
                self._update_config_from_dict(config_data)
                logger.info(f"Configuration loaded from {self.config_path}")
            
            except Exception as e:
                logger.error(f"Failed to load config from {self.config_path}: {e}")
                logger.info("Using default configuration")
        else:
            logger.info(f"Config file {self.config_path} not found, using defaults")
    
    def _update_config_from_dict(self, config_data: Dict[str, Any]):
        """Update configuration from dictionary"""
        
        # Update STT config
        if "stt" in config_data:
            stt_data = config_data["stt"]
            for key, value in stt_data.items():
                if hasattr(self.config.stt, key):
                    setattr(self.config.stt, key, value)
        
        # Update TTS config  
        if "tts" in config_data:
            tts_data = config_data["tts"]
            for key, value in tts_data.items():
                if hasattr(self.config.tts, key):
                    setattr(self.config.tts, key, value)
        
        # Update AI config
        if "ai" in config_data:
            ai_data = config_data["ai"]
            for key, value in ai_data.items():
                if hasattr(self.config.ai, key):
                    setattr(self.config.ai, key, value)
        
        # Update other configs
        for section in ["database", "cache", "logging"]:
            if section in config_data:
                section_config = getattr(self.config, section)
                for key, value in config_data[section].items():
                    if hasattr(section_config, key):
                        setattr(section_config, key, value)
        
        # Update app-level settings
        for key in ["app_name", "version", "debug", "api_host", "api_port", "secret_key", "enable_cors"]:
            if key in config_data:
                setattr(self.config, key, config_data[key])
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        env_mappings = {
            # STT settings
            "STT_PROVIDER": ("stt", "provider"),
            "STT_MODEL": ("stt", "model_name"),
            "STT_DEVICE": ("stt", "device"),
            "STT_HIGH_CONFIDENCE": ("stt", "high_confidence", float),
            
            # TTS settings
            "TTS_PROVIDER": ("tts", "provider"),
            "TTS_MODEL": ("tts", "model_name"),
            "TTS_SPEED": ("tts", "speed", float),
            "TTS_VOLUME": ("tts", "volume", float),
            
            # AI settings
            "AI_MODEL": ("ai", "model_name"),
            "AI_DEVICE": ("ai", "device"),
            "AI_TEMPERATURE": ("ai", "temperature", float),
            "AI_MAX_LENGTH": ("ai", "max_length", int),
            
            # App settings
            "APP_DEBUG": ("debug", bool),
            "APP_HOST": ("api_host"),
            "APP_PORT": ("api_port", int),
            "SECRET_KEY": ("secret_key"),
            
            # Database
            "DB_PATH": ("database", "db_path"),
            
            # Logging
            "LOG_LEVEL": ("logging", "level"),
        }
        
        for env_var, mapping in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                try:
                    # Parse value based on type
                    if len(mapping) > 2:
                        value_type = mapping[2]
                        if value_type == bool:
                            parsed_value = env_value.lower() in ('true', '1', 'yes', 'on')
                        elif value_type in (int, float):
                            parsed_value = value_type(env_value)
                        else:
                            parsed_value = env_value
                    else:
                        parsed_value = env_value
                    
                    # Apply override
                    if len(mapping) >= 2 and isinstance(mapping[0], str) and mapping[0] in ["stt", "tts", "ai", "database", "cache", "logging"]:
                        # Section-based setting
                        section = getattr(self.config, mapping[0])
                        setattr(section, mapping[1], parsed_value)
                    else:
                        # App-level setting
                        setattr(self.config, mapping[0], parsed_value)
                    
                    logger.debug(f"Applied environment override: {env_var}={parsed_value}")
                
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid environment variable value {env_var}={env_value}: {e}")
    
    def save_config(self, config_path: Optional[str] = None):
        """Save current configuration to file"""
        save_path = config_path or self.config_path
        
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Convert config to dictionary
            config_dict = asdict(self.config)
            
            # Save to file
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration saved to {save_path}")
        
        except Exception as e:
            logger.error(f"Failed to save config to {save_path}: {e}")
            raise
    
    def get_config(self) -> AppConfig:
        """Get current configuration"""
        return self.config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values"""
        self._update_config_from_dict(updates)
        logger.info("Configuration updated")
    
    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        self.config = AppConfig()
        logger.info("Configuration reset to defaults")
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate current configuration"""
        issues = []
        
        # Validate STT config
        if self.config.stt.high_confidence <= self.config.stt.medium_confidence:
            issues.append("STT high confidence threshold must be greater than medium")
        
        if self.config.stt.medium_confidence <= self.config.stt.low_confidence:
            issues.append("STT medium confidence threshold must be greater than low")
        
        # Validate TTS config
        if not (0.1 <= self.config.tts.speed <= 3.0):
            issues.append("TTS speed must be between 0.1 and 3.0")
        
        if not (0.0 <= self.config.tts.volume <= 1.0):
            issues.append("TTS volume must be between 0.0 and 1.0")
        
        # Validate AI config
        if not (0.0 <= self.config.ai.temperature <= 2.0):
            issues.append("AI temperature must be between 0.0 and 2.0")
        
        if self.config.ai.max_length < 50:
            issues.append("AI max length should be at least 50 tokens")
        
        # Validate paths
        for path_attr in ["database.db_path", "cache.model_cache_dir", "cache.audio_cache_dir"]:
            path_parts = path_attr.split(".")
            config_obj = self.config
            for part in path_parts:
                config_obj = getattr(config_obj, part)
            
            # Ensure directory exists for the path
            try:
                if path_attr == "database.db_path":
                    os.makedirs(os.path.dirname(config_obj), exist_ok=True)
                else:
                    os.makedirs(config_obj, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory for {path_attr}: {e}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }

# Global configuration instance
_config_manager = None

def get_config() -> AppConfig:
    """Get global configuration instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.get_config()

def get_config_manager() -> ConfigManager:
    """Get global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def reload_config(config_path: Optional[str] = None):
    """Reload configuration from file"""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    logger.info("Configuration reloaded")