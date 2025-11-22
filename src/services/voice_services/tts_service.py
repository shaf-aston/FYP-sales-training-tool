"""
TTS Service - Modular Implementation
Main entry point for Text-to-Speech functionality
"""

# Import all TTS functionality from modular components
from .tts import (
    EnhancedTTSService,
    TTSService,
    get_tts_service,
    TTSResult,
    TTSVoiceProfile,
    TTSCache,
    TextChunker,
    AudioFormatConverter,
    clean_text_for_tts,
    MOSEvaluator
)

# Re-export for compatibility
__all__ = [
    'EnhancedTTSService',
    'TTSService',
    'get_tts_service',
    'TTSResult',
    'TTSVoiceProfile',
    'TTSCache',
    'TextChunker',
    'AudioFormatConverter',
    'clean_text_for_tts',
    'MOSEvaluator'
]