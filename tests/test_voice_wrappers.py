#!/usr/bin/env python3
"""
Minimal tests for route-friendly voice_service wrappers
Validates wrapper outputs and basic fallback behavior without heavy deps.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Light module mocks to avoid heavy imports
sys.modules['whisper'] = MagicMock()
sys.modules['TTS'] = MagicMock()
sys.modules['TTS.api'] = MagicMock()
sys.modules['TTS.api.TTS'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['torch'] = MagicMock()

from services.voice_service import EnhancedVoiceService, VoiceEmotion


def test_synthesize_speech_wrapper_fallback():
    """Wrapper returns dict with base64 audio or None and timings"""
    service = EnhancedVoiceService()
    # Force fallback path for TTS
    service.coqui_tts = None

    async def run():
        return await service.synthesize_speech(
            text="Hello test",
            emotion="friendly",
            speaker_id="female_1"
        )

    result = asyncio.run(run())

    assert isinstance(result, dict)
    assert 'audio_data' in result
    assert 'processing_time' in result
    assert 'quality_score' in result
    # Fallback returns None audio
    assert result['audio_data'] is None or isinstance(result['audio_data'], str)
    assert result['processing_time'] >= 0


def test_transcribe_speech_wrapper_fallback():
    """Wrapper returns dict with text, confidence, emotion, timings"""
    service = EnhancedVoiceService()

    # Provide tiny base64 audio payload
    fake_b64 = "ZmFrZV9hdWRpb19kYXRh"  # "fake_audio_data"

    async def run():
        return await service.transcribe_speech(
            audio_data=fake_b64,
            detect_emotion=True,
            language="en"
        )

    result = asyncio.run(run())

    assert isinstance(result, dict)
    for key in ['text', 'confidence', 'language', 'emotion', 'processing_time']:
        assert key in result
    assert result['processing_time'] >= 0