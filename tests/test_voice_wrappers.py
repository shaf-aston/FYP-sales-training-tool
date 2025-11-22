"""
Minimal tests for route-friendly voice_service wrappers
Validates wrapper outputs and basic fallback behavior without heavy deps.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

sys.modules['whisper'] = MagicMock()
sys.modules['TTS'] = MagicMock()
sys.modules['TTS.api'] = MagicMock()
sys.modules['TTS.api.TTS'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['torch'] = MagicMock()

from src.services.voice_services.voice_service import EnhancedVoiceService, VoiceEmotion


def test_synthesize_speech_wrapper_fallback():
    """Wrapper returns dict with base64 audio or None and timings"""
    service = EnhancedVoiceService()
    service.coqui_tts = None

    async def run():
        result = await service.synthesize_speech(
            text="Hello test",
            emotion="friendly",
            speaker_id="female_1"
        )
        assert result is not None
        return result

    result = asyncio.run(run())

    assert isinstance(result, dict)
    assert 'audio_data' in result
    assert 'processing_time' in result
    assert 'quality_score' in result
    assert result['audio_data'] is None or isinstance(result['audio_data'], str)
    assert result['processing_time'] >= 0


def test_transcribe_speech_wrapper_fallback():
    """Wrapper returns dict with text, confidence, emotion, timings"""
    service = EnhancedVoiceService()

    fake_b64 = "ZmFrZV9hdWRpb19kYXRh" 

    async def run():
        result = await service.transcribe_speech(
            audio_data=fake_b64,
            detect_emotion=True,
            language="en"
        )
        assert result is not None
        return result

    result = asyncio.run(run())

    assert isinstance(result, dict)
    for key in ['text', 'confidence', 'language', 'emotion', 'processing_time']:
        assert key in result
    assert result['processing_time'] >= 0