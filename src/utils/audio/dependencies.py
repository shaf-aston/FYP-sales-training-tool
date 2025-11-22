"""
Audio processing dependencies management
Centralized import handling for all audio-related packages
"""
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Availability flags
WHISPER_AVAILABLE = False
FASTER_WHISPER_AVAILABLE = False
SPEECH_RECOGNITION_AVAILABLE = False
COQUI_AVAILABLE = False
PYTTSX3_AVAILABLE = False
JIWER_AVAILABLE = False
SOUNDFILE_AVAILABLE = False
NOISEREDUCE_AVAILABLE = False
AUDIO_PROCESSING_AVAILABLE = False
PYDUB_AVAILABLE = False

# Global imports
whisper = None
WhisperModel = None
torch = None
np = None
librosa = None
sr = None
AudioSegment = None
sf = None
nr = None
pyttsx3 = None
TTS = None
jiwer = None

def check_whisper():
    """Check and import Whisper dependencies"""
    global WHISPER_AVAILABLE, FASTER_WHISPER_AVAILABLE, whisper, WhisperModel, torch
    
    try:
        import whisper as _whisper
        whisper = _whisper
        WHISPER_AVAILABLE = True
        logger.info("OpenAI Whisper available")
    except ImportError:
        logger.warning("OpenAI Whisper not available")
    
    try:
        from faster_whisper import WhisperModel as _WhisperModel
        WhisperModel = _WhisperModel
        FASTER_WHISPER_AVAILABLE = True
        logger.info("Faster Whisper available")
    except ImportError:
        logger.warning("Faster Whisper not available")
    
    try:
        import torch as _torch
        torch = _torch
    except ImportError:
        logger.warning("PyTorch not available")

def check_speech_recognition():
    """Check and import speech recognition dependencies"""
    global SPEECH_RECOGNITION_AVAILABLE, sr
    
    try:
        import speech_recognition as _sr
        sr = _sr
        SPEECH_RECOGNITION_AVAILABLE = True
        logger.info("SpeechRecognition available")
    except ImportError:
        logger.warning("SpeechRecognition not available")

def check_tts():
    """Check and import TTS dependencies"""
    global COQUI_AVAILABLE, PYTTSX3_AVAILABLE, TTS, pyttsx3
    
    try:
        from TTS.api import TTS as _TTS
        TTS = _TTS
        COQUI_AVAILABLE = True
        logger.info("Coqui TTS available")
    except ImportError:
        logger.warning("Coqui TTS not available")
    
    try:
        import pyttsx3 as _pyttsx3
        pyttsx3 = _pyttsx3
        PYTTSX3_AVAILABLE = True
        logger.info("pyttsx3 available")
    except ImportError:
        logger.warning("pyttsx3 not available")

def check_audio_processing():
    """Check and import audio processing dependencies"""
    global SOUNDFILE_AVAILABLE, AUDIO_PROCESSING_AVAILABLE, PYDUB_AVAILABLE
    global sf, np, AudioSegment, librosa, nr, jiwer
    
    try:
        import soundfile as _sf
        import numpy as _np
        sf = _sf
        np = _np
        SOUNDFILE_AVAILABLE = True
        AUDIO_PROCESSING_AVAILABLE = True
        logger.info("Audio processing libraries available")
    except ImportError:
        logger.warning("Audio processing libraries not available")
    
    try:
        from pydub import AudioSegment as _AudioSegment
        AudioSegment = _AudioSegment
        PYDUB_AVAILABLE = True
        logger.info("Pydub available")
    except ImportError:
        logger.warning("Pydub not available")
    
    try:
        import librosa as _librosa
        librosa = _librosa
        logger.info("Librosa available")
    except ImportError:
        logger.warning("Librosa not available")
    
    try:
        import noisereduce as _nr
        nr = _nr
        NOISEREDUCE_AVAILABLE = True
        logger.info("Noise reduction available")
    except ImportError:
        logger.warning("Noise reduction not available")
    
    try:
        import jiwer as _jiwer
        jiwer = _jiwer
        JIWER_AVAILABLE = True
        logger.info("JIWER available")
    except ImportError:
        logger.warning("JIWER not available")

def initialize_all():
    """Initialize all audio dependencies"""
    check_whisper()
    check_speech_recognition()
    check_tts()
    check_audio_processing()

def get_availability_status() -> Dict[str, bool]:
    """Get status of all audio dependencies"""
    return {
        'whisper': WHISPER_AVAILABLE,
        'faster_whisper': FASTER_WHISPER_AVAILABLE,
        'speech_recognition': SPEECH_RECOGNITION_AVAILABLE,
        'coqui_tts': COQUI_AVAILABLE,
        'pyttsx3': PYTTSX3_AVAILABLE,
        'soundfile': SOUNDFILE_AVAILABLE,
        'audio_processing': AUDIO_PROCESSING_AVAILABLE,
        'pydub': PYDUB_AVAILABLE,
        'noisereduce': NOISEREDUCE_AVAILABLE,
        'jiwer': JIWER_AVAILABLE
    }

# Initialize on import
initialize_all()