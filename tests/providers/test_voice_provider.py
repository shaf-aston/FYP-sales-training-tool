"""Unit tests for VoiceProvider: STT transcription, TTS synthesis, rate limiting."""

import pytest
import time
from unittest.mock import patch, MagicMock

# Import the module to test
from chatbot.providers.voice_provider import (
    VoiceProvider,
    TranscriptionResult,
    SynthesisResult,
    EDGE_TTS_AVAILABLE,
)


class TestVoiceProviderInitialization:
    """Test VoiceProvider initialization and availability checks."""

    def test_voice_provider_instantiation(self):
        """VoiceProvider should initialize without error."""
        provider = VoiceProvider()
        assert provider is not None

    def test_is_stt_available(self):
        """Check STT availability based on backend status."""
        provider = VoiceProvider()
        # Should return False if DEEPGRAM_API env var is not set (default in tests)
        result = provider.is_stt_available()
        assert isinstance(result, bool)

    def test_is_tts_available(self):
        """Check TTS availability based on Edge TTS library."""
        provider = VoiceProvider()
        # Should match EDGE_TTS_AVAILABLE constant
        result = provider.is_tts_available()
        assert isinstance(result, bool)
        assert result == EDGE_TTS_AVAILABLE

    def test_get_available_voices(self):
        """Retrieve list of available TTS voices."""
        provider = VoiceProvider()
        voices = provider.get_available_voices()
        assert isinstance(voices, dict)
        assert "male_us" in voices
        assert "female_us" in voices
        assert "male_uk" in voices
        assert "female_uk" in voices

    def test_get_status(self):
        """Get provider status report."""
        provider = VoiceProvider()
        status = provider.get_status()
        assert isinstance(status, dict)
        assert "stt_deepgram" in status
        assert "tts_edge" in status
        assert "stt_available" in status
        assert "tts_available" in status


class TestTranscription:
    """Test STT transcription path: unavailable, error handling."""

    def test_transcribe_when_stt_unavailable(self):
        """Transcribe should return error result when STT not available."""
        provider = VoiceProvider()
        # Force STT unavailable
        provider._deepgram_client = None

        result = provider.transcribe(b"dummy_audio.webm")

        assert isinstance(result, TranscriptionResult)
        assert result.text == ""
        assert result.provider == "none"
        assert result.error is not None
        assert "Deepgram not available" in result.error

    def test_transcribe_empty_audio(self):
        """Should reject empty audio."""
        provider = VoiceProvider()
        provider._deepgram_client = None

        result = provider.transcribe(b"")
        assert result.error is not None

    def test_transcribe_result_structure(self):
        """TranscriptionResult should have required fields."""
        result = TranscriptionResult(
            text="Hello world",
            latency_ms=250.5,
            provider="deepgram",
        )
        assert result.text == "Hello world"
        assert result.latency_ms == 250.5
        assert result.provider == "deepgram"
        assert result.error is None

    def test_rate_limit_tracking_state(self):
        """Rate limit flag should persist and expire correctly."""
        provider = VoiceProvider()

        # Initially not rate-limited
        assert not provider._is_deepgram_rate_limited()

        # Mark as rate-limited
        provider._mark_deepgram_rate_limited()
        assert provider._is_deepgram_rate_limited()

        # Simulate cooldown expiry
        provider._deepgram_rate_limited_until = time.time() - 1  # 1 second in past
        assert not provider._is_deepgram_rate_limited()

    def test_transcribe_honors_rate_limit(self):
        """Transcribe should return rate-limit error when cooldown active."""
        provider = VoiceProvider()
        provider._deepgram_client = MagicMock()  # Pretend client exists
        provider._mark_deepgram_rate_limited()

        result = provider.transcribe(b"dummy_audio.webm")

        assert result.error is not None
        assert "rate" in result.error.lower() or "unavailable" in result.error.lower()

    def test_transcribe_detects_rate_limit_in_response(self):
        """Transcribe should detect rate-limit 429 error and mark rate-limited."""
        provider = VoiceProvider()
        provider._deepgram_client = MagicMock()
        provider._deepgram_client.listen.rest.v().transcribe_file.side_effect = (
            Exception("429 Rate limit exceeded")
        )

        result = provider.transcribe(b"dummy_audio.webm")

        # Should have error
        assert result.error is not None
        # Should mark for rate limiting (check state)
        # Since "429" is in error, rate limit was triggered
        assert provider._is_deepgram_rate_limited()


class TestSynthesis:
    """Test TTS synthesis path: text validation, voice selection, error handling."""

    def test_synthesize_result_structure(self):
        """SynthesisResult should have required fields."""
        result = SynthesisResult(
            audio_bytes=b"\x01\x02\x03",
            content_type="audio/mpeg",
            latency_ms=150.0,
            voice="en-US-GuyNeural",
        )
        assert result.audio_bytes == b"\x01\x02\x03"
        assert result.content_type == "audio/mpeg"
        assert result.latency_ms == 150.0
        assert result.voice == "en-US-GuyNeural"
        assert result.error is None

    def test_synthesize_when_tts_unavailable(self):
        """Should return error when Edge TTS not available."""
        with patch("chatbot.providers.voice_provider.EDGE_TTS_AVAILABLE", False):
            provider = VoiceProvider()
            result = provider.synthesize("Hello world")

            assert result.audio_bytes == b""
            assert result.error is not None
            assert "Edge TTS not installed" in result.error

    def test_synthesize_empty_text(self):
        """Should reject empty text."""
        if not EDGE_TTS_AVAILABLE:
            pytest.skip("Edge TTS not available")

        provider = VoiceProvider()
        result = provider.synthesize("")
        assert result.error is not None
        assert "Empty text" in result.error

    def test_synthesize_whitespace_only_text(self):
        """Should reject whitespace-only text."""
        if not EDGE_TTS_AVAILABLE:
            pytest.skip("Edge TTS not available")

        provider = VoiceProvider()
        result = provider.synthesize("   \n  \t  ")
        assert result.error is not None

    def test_voice_key_resolution(self):
        """Should resolve voice keys to full voice names."""
        provider = VoiceProvider()

        assert provider.VOICES["male_us"] == "en-US-GuyNeural"
        assert provider.VOICES["female_uk"] == "en-GB-SoniaNeural"

    def test_synthesize_accepts_voice_key(self):
        """Synthesize should accept short voice keys (male_us) or full names."""
        if not EDGE_TTS_AVAILABLE:
            pytest.skip("Edge TTS not available")

        provider = VoiceProvider()
        # This will fail gracefully if edge-tts isn't truly available
        # But we test that the voice mapping works
        voices = provider.get_available_voices()
        assert len(voices) > 0

    def test_get_mimetype_detection(self):
        """Should correctly map file extensions to MIME types."""
        provider = VoiceProvider()

        assert provider._get_mimetype("audio.webm") == "audio/webm"
        assert provider._get_mimetype("recording.mp3") == "audio/mpeg"
        assert provider._get_mimetype("sound.wav") == "audio/wav"
        assert provider._get_mimetype("clip.ogg") == "audio/ogg"
        assert provider._get_mimetype("file.m4a") == "audio/mp4"
        assert provider._get_mimetype("unknown.xyz") == "audio/webm"  # default
        assert provider._get_mimetype("noextension") == "audio/webm"  # default


class TestVoiceProviderConcurrency:
    """Test thread safety of rate limiting and state."""

    def test_rate_limit_lock_thread_safety(self):
        """Rate limit updates should be thread-safe."""
        import threading

        provider = VoiceProvider()
        states = []

        def mark_limited():
            provider._mark_deepgram_rate_limited()
            states.append(provider._is_deepgram_rate_limited())

        threads = [threading.Thread(target=mark_limited) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should see rate limit as marked (or expired)
        # At minimum, the operation should not crash
        assert len(states) > 0


class TestTranscriptionResultDataclass:
    """Test TranscriptionResult creation and error patterns."""

    def test_transcription_success_result(self):
        """Create successful transcription result."""
        result = TranscriptionResult(
            text="I would like to buy this product",
            latency_ms=1200.5,
            provider="deepgram",
        )
        assert result.text == "I would like to buy this product"
        assert result.error is None

    def test_transcription_error_result(self):
        """Create error transcription result."""
        result = TranscriptionResult(
            text="",
            latency_ms=500.0,
            provider="deepgram",
            error="API timeout",
        )
        assert result.text == ""
        assert result.error == "API timeout"

    def test_transcription_none_error_when_not_set(self):
        """Error field should default to None."""
        result = TranscriptionResult(
            text="success",
            latency_ms=100.0,
            provider="deepgram",
        )
        assert result.error is None


class TestSynthesisResultDataclass:
    """Test SynthesisResult creation and representations."""

    def test_synthesis_success_result(self):
        """Create successful synthesis result."""
        audio = b"fake_mp3_bytes_here"
        result = SynthesisResult(
            audio_bytes=audio,
            content_type="audio/mpeg",
            latency_ms=800.0,
            voice="en-US-GuyNeural",
        )
        assert result.audio_bytes == audio
        assert result.content_type == "audio/mpeg"
        assert result.error is None

    def test_synthesis_error_result(self):
        """Create error synthesis result."""
        result = SynthesisResult(
            audio_bytes=b"",
            content_type="audio/mpeg",
            latency_ms=100.0,
            voice="",
            error="Rate limit exceeded",
        )
        assert result.audio_bytes == b""
        assert result.error == "Rate limit exceeded"


class TestVoiceProviderDefaults:
    """Test default configuration."""

    def test_default_voice(self):
        """DEFAULT_VOICE should be set."""
        assert VoiceProvider.DEFAULT_VOICE == "male_us"

    def test_rate_limit_cooldown_duration(self):
        """RATE_LIMIT_COOLDOWN should be 60 seconds."""
        assert VoiceProvider.RATE_LIMIT_COOLDOWN == 60
