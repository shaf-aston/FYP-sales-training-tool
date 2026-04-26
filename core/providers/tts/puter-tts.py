"""Optional Puter text-to-speech fallback provider."""

from __future__ import annotations

import os
import time

from ..base import BaseTTSProvider, SynthesisResult
from ..config import (
    DEFAULT_PUTER_TTS_ENGINE,
    DEFAULT_PUTER_TTS_LANGUAGE,
    DEFAULT_PUTER_TTS_PROVIDER,
    DEFAULT_PUTER_TTS_VOICE,
)

BACKEND_UNAVAILABLE_MESSAGE = (
    "Puter TTS uses the browser SDK in this project and is not available from the backend."
)


class PuterTTSProvider(BaseTTSProvider):
    provider_name = "puter"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("PUTER_TTS_PROVIDER") or DEFAULT_PUTER_TTS_PROVIDER
        self.voice = os.environ.get("PUTER_TTS_VOICE") or DEFAULT_PUTER_TTS_VOICE
        self.language = os.environ.get("PUTER_TTS_LANGUAGE") or DEFAULT_PUTER_TTS_LANGUAGE
        self.engine = os.environ.get("PUTER_TTS_ENGINE") or DEFAULT_PUTER_TTS_ENGINE

    def is_available(self) -> bool:
        return False

    def get_model_name(self) -> str:
        return self.model

    def synthesize(self, text: str, voice: str = "male_us", rate: int = 0) -> SynthesisResult:
        start = time.time()
        return SynthesisResult(
            provider=self.provider_name,
            voice=self.voice,
            error=BACKEND_UNAVAILABLE_MESSAGE,
            latency_ms=(time.time() - start) * 1000,
        )
