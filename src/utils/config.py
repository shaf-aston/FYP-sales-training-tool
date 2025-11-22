"""
Centralized configuration management
Replaces scattered config loading across the project
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SRC_DIR = PROJECT_ROOT / "src"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"

# Create directories if they don't exist
LOGS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

@dataclass
class AppConfig:
    """Main application configuration"""
    title: str = "Sales Roleplay Chatbot"
    version: str = "1.0.0"
    debug: bool = False
    cors_origins: list = None
    
    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]

@dataclass 
class DatabaseConfig:
    """Database configuration"""
    url: str = "sqlite:///./sales_chatbot.db"
    echo: bool = False
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class VoiceConfig:
    """Voice services configuration"""
    stt_model: str = "base"
    stt_provider: str = "faster_whisper" 
    tts_model: str = "tts_models/en/ljspeech/tacotron2-DDC"
    tts_provider: str = "coqui"
    cache_enabled: bool = True
    cache_size: int = 100
    cache_ttl: int = 3600

@dataclass
class AIConfig:
    """AI model configuration"""
    model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"
    max_tokens: int = 512
    temperature: float = 0.7
    device: str = "auto"
    cache_dir: Optional[str] = None
    
    def __post_init__(self):
        if self.cache_dir is None:
            self.cache_dir = str(PROJECT_ROOT / "model_cache")

class ConfigManager:
    """Centralized configuration manager"""
    
    def __init__(self):
        self.app = AppConfig()
        self.database = DatabaseConfig()
        self.voice = VoiceConfig()
        self.ai = AIConfig()
        self._load_from_files()
        self._load_from_env()
    
    def _load_from_files(self):
        """Load configuration from JSON files"""
        try:
            # Load app config
            app_config_path = CONFIG_DIR / "app.json"
            if app_config_path.exists():
                with open(app_config_path) as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.app, key):
                            setattr(self.app, key, value)
            
            # Load voice config
            voice_config_path = CONFIG_DIR / "voice.json"
            if voice_config_path.exists():
                with open(voice_config_path) as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.voice, key):
                            setattr(self.voice, key, value)
            
            # Load AI config
            ai_config_path = CONFIG_DIR / "ai.json"
            if ai_config_path.exists():
                with open(ai_config_path) as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self.ai, key):
                            setattr(self.ai, key, value)
                            
        except Exception as e:
            logger.warning(f"Failed to load config files: {e}")
    
    def _load_from_env(self):
        """Load configuration from environment variables"""
        # App config
        self.app.debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Database config  
        self.database.url = os.getenv("DATABASE_URL", self.database.url)
        
        # Voice config
        self.voice.stt_model = os.getenv("STT_MODEL", self.voice.stt_model)
        self.voice.tts_model = os.getenv("TTS_MODEL", self.voice.tts_model)
        
        # AI config
        self.ai.model_name = os.getenv("AI_MODEL", self.ai.model_name)
        self.ai.device = os.getenv("AI_DEVICE", self.ai.device)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return {
            "app": {
                "title": self.app.title,
                "version": self.app.version,
                "debug": self.app.debug,
                "cors_origins": self.app.cors_origins
            },
            "database": {
                "url": self.database.url,
                "echo": self.database.echo
            },
            "voice": {
                "stt_model": self.voice.stt_model,
                "stt_provider": self.voice.stt_provider,
                "tts_model": self.voice.tts_model,
                "tts_provider": self.voice.tts_provider,
                "cache_enabled": self.voice.cache_enabled
            },
            "ai": {
                "model_name": self.ai.model_name,
                "max_tokens": self.ai.max_tokens,
                "temperature": self.ai.temperature,
                "device": self.ai.device
            }
        }
    
    def save_config(self, config_type: str = None):
        """Save configuration to files"""
        try:
            CONFIG_DIR.mkdir(exist_ok=True)
            
            if config_type is None or config_type == "app":
                with open(CONFIG_DIR / "app.json", "w") as f:
                    json.dump(self.get_config_dict()["app"], f, indent=2)
            
            if config_type is None or config_type == "voice":
                with open(CONFIG_DIR / "voice.json", "w") as f:
                    json.dump(self.get_config_dict()["voice"], f, indent=2)
            
            if config_type is None or config_type == "ai":
                with open(CONFIG_DIR / "ai.json", "w") as f:
                    json.dump(self.get_config_dict()["ai"], f, indent=2)
                    
            logger.info(f"Saved configuration: {config_type or 'all'}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

# Global configuration instance
config = ConfigManager()

# Legacy compatibility
APP_TITLE = config.app.title
APP_VERSION = config.app.version
CORS_ORIGINS = config.app.cors_origins
STATIC_DIR = PROJECT_ROOT / "static"

def get_config() -> ConfigManager:
    """Get global configuration instance"""
    return config

def update_config(**kwargs):
    """Update configuration values"""
    for key, value in kwargs.items():
        if hasattr(config.app, key):
            setattr(config.app, key, value)
        elif hasattr(config.voice, key):
            setattr(config.voice, key, value)
        elif hasattr(config.ai, key):
            setattr(config.ai, key, value)
        else:
            logger.warning(f"Unknown config key: {key}")