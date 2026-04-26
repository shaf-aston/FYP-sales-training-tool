"""Optional Puter speech-to-text fallback provider."""

from __future__ import annotations

import os
import time

from ..base import BaseSTTProvider, TranscriptionResult
from ..config import DEFAULT_PUTER_STT_MODEL

BACKEND_UNAVAILABLE_MESSAGE = (
    "Puter STT uses the browser SDK in this project and is not available from the backend."
)


class PuterSTTProvider(BaseSTTProvider):
    provider_name = "puter"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("PUTER_STT_MODEL") or DEFAULT_PUTER_STT_MODEL

    def is_available(self) -> bool:
        return False

    def get_model_name(self) -> str:
        return self.model

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> TranscriptionResult:
        start = time.time()
        return TranscriptionResult(
            provider=self.provider_name,
            error=BACKEND_UNAVAILABLE_MESSAGE,
            latency_ms=(time.time() - start) * 1000,
        )
