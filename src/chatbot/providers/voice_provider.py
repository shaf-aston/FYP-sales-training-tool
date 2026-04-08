"""Voice provider - Deepgram STT (primary) + Groq Whisper (backup) + Edge TTS

Provides unified speech-to-text and text-to-speech for voice mode.
Handles automatic failover from Deepgram to Groq Whisper when rate-limited.
"""

import os
import time
import asyncio
import logging
import threading
import atexit
import importlib.util
from dataclasses import dataclass
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ============================================================================
# Persistent Event Loop (avoids asyncio.run() per request)
# ============================================================================
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None
_loop_lock = threading.Lock()


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """Get or create a persistent event loop running on a background thread."""
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is None or not _loop.is_running():
            _loop = asyncio.new_event_loop()

            def _run_loop():
                assert _loop is not None  # Type narrowing
                asyncio.set_event_loop(_loop)
                _loop.run_forever()

            _loop_thread = threading.Thread(target=_run_loop, daemon=True)
            _loop_thread.start()
            logger.info("VoiceProvider: Started persistent async event loop")
    assert _loop is not None  # Type narrowing before return
    return _loop


def _run_async(coro: Any) -> Any:
    """Run a coroutine on the persistent event loop and wait for result."""
    loop = _get_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)  # 30s timeout for TTS


def _shutdown_event_loop():
    """Gracefully stop the event loop on process exit."""
    global _loop
    if _loop and _loop.is_running():
        _loop.call_soon_threadsafe(_loop.stop)
        logger.info("VoiceProvider: Stopped async event loop")


atexit.register(_shutdown_event_loop)

# Check for Deepgram SDK
try:
    from deepgram import DeepgramClient
    DEEPGRAM_AVAILABLE = True
except ImportError:
    DEEPGRAM_AVAILABLE = False
    logger.warning("Deepgram SDK not installed. Run: pip install deepgram-sdk")

# Check for Groq SDK (for Whisper backup)
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Check for Edge TTS
EDGE_TTS_AVAILABLE = importlib.util.find_spec("edge_tts") is not None
if not EDGE_TTS_AVAILABLE:
    logger.warning("Edge TTS not installed. Run: pip install edge-tts")


@dataclass
class TranscriptionResult:
    """Result of speech-to-text transcription"""
    text: str
    latency_ms: float
    provider: str  # "deepgram" or "groq_whisper"
    error: Optional[str] = None


@dataclass
class SynthesisResult:
    """Result of text-to-speech synthesis"""
    audio_bytes: bytes
    content_type: str
    latency_ms: float
    voice: str
    error: Optional[str] = None


class VoiceProvider:
    """Unified voice provider: Deepgram STT (primary) + Groq Whisper (backup) + Edge TTS

    STT Failover:
        - Try Deepgram first (lower latency: 200-500ms)
        - If rate-limited or fails, switch to Groq Whisper (backup)
        - Track rate limit state to avoid repeated failures

    TTS:
        - Edge TTS (Microsoft neural voices, free unlimited)
    """

    # Edge TTS voice options (professional sales training)
    VOICES = {
        "male_us": "en-US-GuyNeural",
        "female_us": "en-US-JennyNeural",
        "male_uk": "en-GB-RyanNeural",
        "female_uk": "en-GB-SoniaNeural",
    }
    DEFAULT_VOICE = "male_us"

    # Rate limit cooldown (seconds)
    RATE_LIMIT_COOLDOWN = 60

    def __init__(self, whisper_model: str = "whisper-large-v3-turbo"):
        """Initialize voice provider with optional Whisper model override."""
        self._whisper_model = whisper_model

        # Deepgram client (primary STT)
        self._deepgram_api_key = os.environ.get("DEEPGRAM_API", "").strip()
        self._deepgram_client = None
        if DEEPGRAM_AVAILABLE and self._deepgram_api_key:
            try:
                self._deepgram_client = DeepgramClient(self._deepgram_api_key)  # type: ignore
                logger.info("Deepgram STT initialized (primary)")
            except Exception as e:
                logger.warning(f"Deepgram init failed: {e}")

        # Groq client (backup STT via Whisper)
        self._groq_api_key = os.environ.get("GROQ_WHISPER_KEY", "").strip()
        
        self._groq_client = None
        if GROQ_AVAILABLE and self._groq_api_key:
            try:
                self._groq_client = Groq(api_key=self._groq_api_key)  # type: ignore
                logger.info("Groq Whisper STT initialized (backup)")
            except Exception as e:
                logger.warning(f"Groq Whisper init failed: {e}")

        # Rate limit tracking
        self._deepgram_rate_limited_until: float = 0
        self._rate_limit_lock = threading.Lock()

        # Log availability status
        self._log_availability()

    def _log_availability(self) -> None:
        """Log which providers are available."""
        status = []
        if self._deepgram_client:
            status.append("Deepgram (primary)")
        if self._groq_client:
            status.append("Groq Whisper (backup)")
        if EDGE_TTS_AVAILABLE:
            status.append("Edge TTS")

        if status:
            logger.info(f"VoiceProvider ready: {', '.join(status)}")
        else:
            logger.error("VoiceProvider: No providers available!")

    def is_stt_available(self) -> bool:
        """Check if at least one STT provider is available."""
        return self._deepgram_client is not None or self._groq_client is not None

    def is_tts_available(self) -> bool:
        """Check if TTS is available."""
        return EDGE_TTS_AVAILABLE

    def _is_deepgram_rate_limited(self) -> bool:
        """Check if Deepgram is currently rate-limited."""
        with self._rate_limit_lock:
            return time.time() < self._deepgram_rate_limited_until

    def _mark_deepgram_rate_limited(self) -> None:
        """Mark Deepgram as rate-limited for cooldown period."""
        with self._rate_limit_lock:
            self._deepgram_rate_limited_until = time.time() + self.RATE_LIMIT_COOLDOWN
            logger.warning(f"Deepgram rate-limited, cooling down for {self.RATE_LIMIT_COOLDOWN}s")

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> TranscriptionResult:
        """Transcribe audio to text using Deepgram (primary) or Groq Whisper (backup).

        Args:
            audio_bytes: Raw audio data (webm, wav, mp3, etc.)
            filename: Original filename for format detection

        Returns:
            TranscriptionResult with text, latency, provider used, and any error
        """
        if not self.is_stt_available():
            return TranscriptionResult(
                text="",
                latency_ms=0,
                provider="none",
                error="No STT providers available. Check DEEPGRAM_API or GROQ_WHISPER_KEY env vars."
            )

        # Try Deepgram first (if not rate-limited)
        if self._deepgram_client and not self._is_deepgram_rate_limited():
            result = self._transcribe_deepgram(audio_bytes, filename)
            if result.error is None:
                return result
            # Check if rate-limited
            if "rate" in result.error.lower() or "429" in result.error:
                self._mark_deepgram_rate_limited()
            else:
                logger.warning(f"Deepgram failed ({result.error}), trying Groq Whisper")

        # Fallback to Groq Whisper
        if self._groq_client:
            return self._transcribe_groq_whisper(audio_bytes, filename)

        return TranscriptionResult(
            text="",
            latency_ms=0,
            provider="none",
            error="All STT providers failed or unavailable"
        )

    def _transcribe_deepgram(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        """Transcribe using Deepgram API (v6 SDK)."""
        assert self._deepgram_client is not None  # Type narrowing: caller checks before calling
        start = time.time()
        try:
            # Deepgram v6 SDK uses different API structure
            options = {
                "model": "nova-2",
                "smart_format": True,
                "language": "en",
            }

            # Create source from bytes
            source = {"buffer": audio_bytes, "mimetype": self._get_mimetype(filename)}

            # Transcribe using listen.rest.v1
            response = self._deepgram_client.listen.rest.v("1").transcribe_file(  # type: ignore[attr-defined]
                source, options
            )

            # Extract text from response
            text = ""
            if hasattr(response, 'results') and response.results:
                channels = response.results.channels
                if channels and len(channels) > 0:
                    alternatives = channels[0].alternatives
                    if alternatives and len(alternatives) > 0:
                        text = alternatives[0].transcript

            latency = (time.time() - start) * 1000
            logger.info(f"Deepgram transcription: {latency:.0f}ms, {len(text)} chars")

            return TranscriptionResult(
                text=text.strip(),
                latency_ms=latency,
                provider="deepgram"
            )

        except Exception as e:
            logger.error(f"Deepgram transcription error: {e}")
            return TranscriptionResult(
                text="",
                latency_ms=(time.time() - start) * 1000,
                provider="deepgram",
                error=str(e)
            )

    def _transcribe_groq_whisper(self, audio_bytes: bytes, filename: str) -> TranscriptionResult:
        """Transcribe using Groq Whisper API (backup)."""
        assert self._groq_client is not None  # Type narrowing: caller checks before calling
        start = time.time()
        try:
            response = self._groq_client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=self._whisper_model,
                response_format="text"
            )

            latency = (time.time() - start) * 1000
            text = response.strip() if isinstance(response, str) else str(response).strip()
            logger.info(f"Groq Whisper transcription: {latency:.0f}ms, {len(text)} chars")

            return TranscriptionResult(
                text=text,
                latency_ms=latency,
                provider="groq_whisper"
            )

        except Exception as e:
            logger.error(f"Groq Whisper transcription error: {e}")
            return TranscriptionResult(
                text="",
                latency_ms=(time.time() - start) * 1000,
                provider="groq_whisper",
                error=str(e)
            )

    def synthesize(self, text: str, voice: str | None = None) -> SynthesisResult:
        """Synthesize speech from text using Edge TTS.

        Args:
            text: Text to speak
            voice: Voice key (male_us, female_us, male_uk, female_uk) or full voice name

        Returns:
            SynthesisResult with audio bytes, content type, latency, and any error
        """
        if not EDGE_TTS_AVAILABLE:
            return SynthesisResult(
                audio_bytes=b"",
                content_type="audio/mpeg",
                latency_ms=0,
                voice="",
                error="Edge TTS not installed. Run: pip install edge-tts"
            )

        if not text or not text.strip():
            return SynthesisResult(
                audio_bytes=b"",
                content_type="audio/mpeg",
                latency_ms=0,
                voice="",
                error="Empty text provided"
            )

        # Resolve voice name
        voice_key = voice or self.DEFAULT_VOICE
        voice_name = self.VOICES.get(voice_key, voice_key)  # Allow direct voice names too

        start = time.time()
        try:
            # Run async edge-tts on persistent event loop (avoids asyncio.run() overhead)
            audio_bytes = _run_async(self._generate_audio(text, voice_name))
            latency = (time.time() - start) * 1000

            logger.info(f"Edge TTS synthesis: {latency:.0f}ms, {len(audio_bytes)} bytes, voice={voice_name}")

            return SynthesisResult(
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
                latency_ms=latency,
                voice=voice_name
            )

        except Exception as e:
            logger.error(f"Edge TTS synthesis error: {e}")
            return SynthesisResult(
                audio_bytes=b"",
                content_type="audio/mpeg",
                latency_ms=(time.time() - start) * 1000,
                voice=voice_name,
                error=str(e)
            )

    async def _generate_audio(self, text: str, voice: str) -> bytes:
        """Generate audio using edge-tts async."""
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        audio_chunks = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk.get("data", b""))

        return b"".join(audio_chunks)

    def _get_mimetype(self, filename: str) -> str:
        """Get MIME type from filename extension."""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        mimetypes = {
            "webm": "audio/webm",
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
        }
        return mimetypes.get(ext, "audio/webm")

    def get_available_voices(self) -> dict:
        """Return available voice options."""
        return self.VOICES.copy()

    def get_status(self) -> dict:
        """Return provider status for debugging/health checks."""
        return {
            "stt_deepgram": self._deepgram_client is not None,
            "stt_groq_whisper": self._groq_client is not None,
            "stt_deepgram_rate_limited": self._is_deepgram_rate_limited(),
            "tts_edge": EDGE_TTS_AVAILABLE,
            "stt_available": self.is_stt_available(),
            "tts_available": self.is_tts_available(),
        }
