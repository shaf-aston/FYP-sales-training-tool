"""
Voice service configuration, enums, and dependency management
Centralizes all voice-related imports and availability checks
"""
import os
import logging
from enum import Enum
from pathlib import Path

# Core dependencies that should always be available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("NumPy not available - some features will be limited")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not available - falling back to CPU-only mode")

# Google Cloud Speech-to-Text (PRIMARY STT SERVICE)
try:
    from google.cloud import speech
    GOOGLE_CLOUD_STT_AVAILABLE = True
    logging.info("✅ Google Cloud Speech-to-Text loaded successfully")
except ImportError:
    GOOGLE_CLOUD_STT_AVAILABLE = False
    logging.info("ℹ️  Google Cloud STT not available - basic fallback will be used")
    logging.info("   To enable: pip install google-cloud-speech")

# Coqui TTS (OPTIONAL)
try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
    logging.info("✅ Coqui TTS loaded successfully")
except ImportError:
    COQUI_AVAILABLE = False
    logging.info("ℹ️  Coqui TTS not available - text-to-speech will use simple fallback")
    logging.info("   To enable: pip install coqui-tts")

# Audio processing libraries (OPTIONAL)
try:
    import librosa
    LIBROSA_AVAILABLE = True
    logging.info("✅ Librosa loaded successfully")
except ImportError:
    LIBROSA_AVAILABLE = False
    logging.info("ℹ️  Librosa not available - advanced audio processing disabled")
    logging.info("   To enable: pip install librosa")

try:
    import scipy.io.wavfile as wavfile
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logging.info("ℹ️  SciPy not available - some audio features limited")

# Local TTS providers
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
    logging.info("✅ pyttsx3 available for offline TTS")
except Exception:
    PYTTSX3_AVAILABLE = False

# Transcript processor
try:
    from services.transcript_processor import get_transcript_processor
    TRANSCRIPT_PROCESSOR_AVAILABLE = True
except Exception:
    TRANSCRIPT_PROCESSOR_AVAILABLE = False
    logging.warning("Transcript processor not available")

# Configuration flags for external services (disabled for local operation)
ELEVENLABS_AVAILABLE = False  # Disabled for local-only operation
GTTS_AVAILABLE = False        # Disabled for offline operation
HUGGINGFACE_AVAILABLE = False # Disabled - using local models only

class VoiceEmotion(Enum):
    """Emotion types for voice synthesis"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    CALM = "calm"
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"

class VoiceConfig:
    """Voice service configuration constants"""
    
    # Cache settings
    MAX_CACHE_SIZE = 1000
    CACHE_TTL_HOURS = 24
    
    # Audio processing settings
    DEFAULT_SAMPLE_RATE = 16000
    MAX_AUDIO_LENGTH_SECONDS = 300
    
    # Performance settings
    MAX_CONCURRENT_REQUESTS = 5
    TIMEOUT_SECONDS = 30
    
    # File paths
    CACHE_DIR = Path("model_cache/stt_cache")
    TTS_CACHE_DIR = Path("model_cache/tts_cache")
    
    # Google Cloud settings
    GOOGLE_CLOUD_ENCODING = "LINEAR16"
    GOOGLE_CLOUD_SAMPLE_RATE = 16000
    
    # Emotion profiles for different voice characteristics
    EMOTION_PROFILES = {
        VoiceEmotion.NEUTRAL: {
            "pitch": 0.0,
            "speed": 1.0,
            "volume": 0.8,
            "emphasis": 0.0
        },
        VoiceEmotion.HAPPY: {
            "pitch": 0.2,
            "speed": 1.1,
            "volume": 0.9,
            "emphasis": 0.3
        },
        VoiceEmotion.SAD: {
            "pitch": -0.2,
            "speed": 0.8,
            "volume": 0.6,
            "emphasis": -0.2
        },
        VoiceEmotion.ANGRY: {
            "pitch": 0.1,
            "speed": 1.2,
            "volume": 1.0,
            "emphasis": 0.5
        },
        VoiceEmotion.EXCITED: {
            "pitch": 0.3,
            "speed": 1.3,
            "volume": 1.0,
            "emphasis": 0.4
        },
        VoiceEmotion.CALM: {
            "pitch": -0.1,
            "speed": 0.9,
            "volume": 0.7,
            "emphasis": -0.1
        },
        VoiceEmotion.PROFESSIONAL: {
            "pitch": 0.0,
            "speed": 1.0,
            "volume": 0.8,
            "emphasis": 0.1
        },
        VoiceEmotion.FRIENDLY: {
            "pitch": 0.1,
            "speed": 1.05,
            "volume": 0.85,
            "emphasis": 0.2
        }
    }

def get_available_services():
    """Return dictionary of available voice services"""
    return {
        "stt": {
            "google_cloud": GOOGLE_CLOUD_STT_AVAILABLE,
            "transcript_processor": TRANSCRIPT_PROCESSOR_AVAILABLE
        },
        "tts": {
            "coqui": COQUI_AVAILABLE,
            "pyttsx3": PYTTSX3_AVAILABLE,
            "elevenlabs": ELEVENLABS_AVAILABLE,
            "gtts": GTTS_AVAILABLE,
            "huggingface": HUGGINGFACE_AVAILABLE
        },
        "audio_processing": {
            "librosa": LIBROSA_AVAILABLE,
            "scipy": SCIPY_AVAILABLE,
            "numpy": NUMPY_AVAILABLE,
            "torch": TORCH_AVAILABLE
        }
    }

def log_service_status():
    """Log the status of all voice services"""
    services = get_available_services()
    
    logging.info("🎤 Voice Service Status:")
    logging.info(f"  STT - Google Cloud: {'✅' if services['stt']['google_cloud'] else '❌'}")
    logging.info(f"  TTS - Coqui: {'✅' if services['tts']['coqui'] else '❌'}")
    logging.info(f"  TTS - pyttsx3: {'✅' if services['tts']['pyttsx3'] else '❌'}")
    logging.info(f"  Audio - Librosa: {'✅' if services['audio_processing']['librosa'] else '❌'}")
    logging.info(f"  Audio - SciPy: {'✅' if services['audio_processing']['scipy'] else '❌'}")