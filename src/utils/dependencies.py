"""
Dependency Management
Handles optional library imports and availability checking
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Global availability flags
DEPENDENCIES = {
    "whisper": False,
    "faster_whisper": False,
    "speech_recognition": False,
    "coqui_tts": False,
    "pyttsx3": False,
    "torch": False,
    "transformers": False,
    "soundfile": False,
    "librosa": False
}

# Global module references
whisper = None
WhisperModel = None
sr = None
TTS = None
pyttsx3 = None
torch = None
transformers = None
sf = None
librosa = None

def check_whisper():
    """Check Whisper availability"""
    global whisper, DEPENDENCIES
    try:
        import whisper as _whisper
        whisper = _whisper
        DEPENDENCIES["whisper"] = True
        logger.info("OpenAI Whisper available")
    except ImportError:
        logger.warning("OpenAI Whisper not available")

def check_faster_whisper():
    """Check Faster Whisper availability"""
    global WhisperModel, DEPENDENCIES
    try:
        from faster_whisper import WhisperModel as _WhisperModel
        WhisperModel = _WhisperModel
        DEPENDENCIES["faster_whisper"] = True
        logger.info("Faster Whisper available")
    except ImportError:
        logger.warning("Faster Whisper not available")

def check_speech_recognition():
    """Check SpeechRecognition availability"""
    global sr, DEPENDENCIES
    try:
        import speech_recognition as _sr
        sr = _sr
        DEPENDENCIES["speech_recognition"] = True
        logger.info("SpeechRecognition available")
    except ImportError:
        logger.warning("SpeechRecognition not available")

def check_coqui_tts():
    """Check Coqui TTS availability"""
    global TTS, DEPENDENCIES
    try:
        from TTS.api import TTS as _TTS
        TTS = _TTS
        DEPENDENCIES["coqui_tts"] = True
        logger.info("Coqui TTS available")
    except ImportError:
        logger.warning("Coqui TTS not available")

def check_pyttsx3():
    """Check pyttsx3 availability"""
    global pyttsx3, DEPENDENCIES
    try:
        import pyttsx3 as _pyttsx3
        pyttsx3 = _pyttsx3
        DEPENDENCIES["pyttsx3"] = True
        logger.info("pyttsx3 available")
    except ImportError:
        logger.warning("pyttsx3 not available")

def check_torch():
    """Check PyTorch availability"""
    global torch, DEPENDENCIES
    try:
        import torch as _torch
        torch = _torch
        DEPENDENCIES["torch"] = True
        logger.info("PyTorch available")
    except ImportError:
        logger.warning("PyTorch not available")

def check_transformers():
    """Check Transformers availability"""
    global transformers, DEPENDENCIES
    try:
        import transformers as _transformers
        transformers = _transformers
        DEPENDENCIES["transformers"] = True
        logger.info("Transformers available")
    except ImportError:
        logger.warning("Transformers not available")

def check_audio_libs():
    """Check audio processing libraries"""
    global sf, librosa, DEPENDENCIES
    try:
        import soundfile as _sf
        sf = _sf
        DEPENDENCIES["soundfile"] = True
        logger.info("Soundfile available")
    except ImportError:
        logger.warning("Soundfile not available")
    
    try:
        import librosa as _librosa
        librosa = _librosa
        DEPENDENCIES["librosa"] = True
        logger.info("Librosa available")
    except ImportError:
        logger.warning("Librosa not available")

def initialize_all():
    """Initialize all dependencies"""
    check_whisper()
    check_faster_whisper()
    check_speech_recognition()
    check_coqui_tts()
    check_pyttsx3()
    check_torch()
    check_transformers()
    check_audio_libs()

def get_available_providers() -> Dict[str, bool]:
    """Get available service providers"""
    return {
        "stt": {
            "whisper": DEPENDENCIES["whisper"],
            "faster_whisper": DEPENDENCIES["faster_whisper"],
            "speech_recognition": DEPENDENCIES["speech_recognition"]
        },
        "tts": {
            "coqui": DEPENDENCIES["coqui_tts"],
            "pyttsx3": DEPENDENCIES["pyttsx3"]
        },
        "ai": {
            "transformers": DEPENDENCIES["transformers"],
            "torch": DEPENDENCIES["torch"]
        }
    }

def validate_provider(service: str, provider: str) -> bool:
    """Validate if a provider is available for a service"""
    providers = get_available_providers()
    return providers.get(service, {}).get(provider, False)

# Initialize on import
initialize_all()