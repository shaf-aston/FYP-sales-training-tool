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
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="edge-tts-worker",
            daemon=True,
        )
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()


class EdgeTTSProvider(BaseTTSProvider):
    provider_name = "edge"

    def __init__(self):
        self._worker: _AsyncWorker | None = None

    def _ensure_worker(self) -> _AsyncWorker:
        if self._worker is None:
            self._worker = _AsyncWorker()
        return self._worker

    async def _synthesize_async(self, text: str, voice_name: str, rate: int):
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
        try:
            importlib.import_module("edge_tts")
            return True
        except ImportError:
            return False

    def get_model_name(self) -> str:
        return "edge-tts"

    def synthesize(self, text: str, voice: str = "male_us", rate: int = 0) -> SynthesisResult:
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
