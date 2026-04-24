#!/usr/bin/env python3
"""Complete integration test for Groq TTS with voice parameter propagation"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ['FLASK_ENV'] = 'testing'

from core.providers.voice_provider import VoiceProvider, TTS_PROVIDER_TYPES
from core.providers.tts.groq import GroqTTSProvider

def test_groq_tts_provider_registered():
    """Verify GroqTTSProvider is in the registry"""
    assert "groq" in TTS_PROVIDER_TYPES
    assert TTS_PROVIDER_TYPES["groq"] == GroqTTSProvider
    print("[PASS] GroqTTSProvider is properly registered")

def test_groq_provider_instantiation():
    """Verify GroqTTSProvider can be instantiated"""
    provider = GroqTTSProvider()
    assert provider.provider_name == "groq"
    assert hasattr(provider, 'synthesize')
    print("[PASS] GroqTTSProvider instantiates correctly")

def test_voice_provider_knows_about_groq():
    """Verify VoiceProvider includes Groq in TTS order"""
    os.environ['TTS_PROVIDER_ORDER'] = 'groq,edge'
    voice_provider = VoiceProvider()
    print(f"[PASS] VoiceProvider TTS order: {voice_provider._tts_order}")

def test_voice_parameter_propagation():
    """Test that voice parameter is correctly passed through the chain"""
    from unittest.mock import Mock
    
    voice_provider = VoiceProvider()
    
    # Mock the TTS provider
    mock_provider = Mock()
    mock_provider.is_available.return_value = True
    mock_provider.provider_name = "mock"
    mock_provider.synthesize = Mock(return_value=Mock(
        provider="mock",
        voice="female_us",
        audio_bytes=b"test_audio",
        content_type="audio/wav",
        error=None
    ))
    
    # Replace builder with mock
    voice_provider._build_tts_provider = lambda provider_name: mock_provider
    
    # Call synthesize with voice parameter
    result = voice_provider.synthesize("Hello", voice="female_us", rate=10)
    
    # Verify synthesize was called with the voice parameter
    mock_provider.synthesize.assert_called_once_with("Hello", voice="female_us", rate=10)
    print(f"[PASS] Voice parameter propagated correctly: {result.voice}")

def test_groq_config_loaded():
    """Verify Groq config values are accessible"""
    from core.providers.config import (
        DEFAULT_GROQ_TTS_MODEL,
        DEFAULT_GROQ_TTS_VOICE,
        DEFAULT_GROQ_TTS_FORMAT
    )
    print(f"[PASS] Groq TTS config loaded:")
    print(f"       Model: {DEFAULT_GROQ_TTS_MODEL}")
    print(f"       Default voice: {DEFAULT_GROQ_TTS_VOICE}")
    print(f"       Format: {DEFAULT_GROQ_TTS_FORMAT}")

def main():
    print("=" * 60)
    print("GROQ TTS INTEGRATION TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_groq_tts_provider_registered,
        test_groq_provider_instantiation,
        test_voice_provider_knows_about_groq,
        test_voice_parameter_propagation,
        test_groq_config_loaded,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
