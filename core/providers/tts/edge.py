"""Optional local Edge TTS fallback provider."""

from __future__ import annotations

import asyncio
import importlib
import threading
import time
from io import BytesIO

from ..base import BaseTTSProvider, SynthesisResult

DEFAULT_VOICE_MAP = {
    "male_us": "en-US-GuyNeural",
    "female_us": "en-US-JennyNeural",
}


class _AsyncWorker:
    def __init__(self):
        """Start a dedicated asyncio loop for background Edge TTS work."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="edge-tts-worker",
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self):
        """Run the worker event loop forever on the background thread."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        """Execute one coroutine on the worker loop and wait for the result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()


class EdgeTTSProvider(BaseTTSProvider):
    provider_name = "edge"

    def __init__(self, model: str | None = None):
        """Initialise the Edge TTS provider and lazy worker state."""
        self._worker: _AsyncWorker | None = None
        self.model = model or "edge-tts"

    def _ensure_worker(self) -> _AsyncWorker:
        """Create the background async worker on first use."""
        if self._worker is None:
            self._worker = _AsyncWorker()
        return self._worker

    async def _synthesize_async(self, text: str, voice_name: str, rate: int):
        """Run the Edge TTS streaming API and collect audio bytes."""
        edge_tts = importlib.import_module("edge_tts")
        audio_buffer = BytesIO()
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_name,
            rate=f"{rate:+d}%",
        )
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])
        return audio_buffer.getvalue()

    def is_available(self) -> bool:
        """Return True when the optional `edge_tts` package is installed."""
        try:
            importlib.import_module("edge_tts")
            return True
        except ImportError:
            return False

    def get_model_name(self) -> str:
        """Return the model label reported for Edge TTS."""
        return self.model

    def synthesize(self, text: str, voice: str = "male_us", rate: int = 0) -> SynthesisResult:
        """Generate speech audio with Edge TTS and return it as bytes."""
        start = time.time()
        voice_name = DEFAULT_VOICE_MAP.get(voice, DEFAULT_VOICE_MAP["male_us"])
        if not self.is_available():
            return SynthesisResult(
                provider=self.provider_name,
                voice=voice_name,
                error="Edge TTS is unavailable.",
                latency_ms=(time.time() - start) * 1000,
            )
        try:
            audio_bytes = self._ensure_worker().run(
                self._synthesize_async(text=text, voice_name=voice_name, rate=rate)
            )
            return SynthesisResult(
                provider=self.provider_name,
                voice=voice_name,
                audio_bytes=audio_bytes,
                content_type="audio/mpeg",
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return SynthesisResult(
                provider=self.provider_name,
                voice=voice_name,
                error=f"Edge TTS synthesis failed: {exc}",
                latency_ms=(time.time() - start) * 1000,
            )
