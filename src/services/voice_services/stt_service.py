"""
STT Service - Modular Implementation  
Main entry point for Speech-to-Text functionality
"""

# Import all STT functionality from modular components
from .stt import (
    EnhancedSTTService,
    get_stt_service,
    STTResult,
    STTCache,
    AudioPreprocessor,
    WhisperBackend,
    FasterWhisperBackend,
    SpeechRecognitionBackend,
    GoogleCloudSTTBackend
)

# Re-export for compatibility
__all__ = [
    'EnhancedSTTService',
    'get_stt_service',
    'STTResult',
    'STTCache',
    'AudioPreprocessor',
    'WhisperBackend', 
    'FasterWhisperBackend',
    'SpeechRecognitionBackend',
    'GoogleCloudSTTBackend'
]