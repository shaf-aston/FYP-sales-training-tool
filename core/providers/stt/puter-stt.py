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
        """Store the configured browser-side Puter STT model label."""
        self.model = model or os.environ.get("PUTER_STT_MODEL") or DEFAULT_PUTER_STT_MODEL

    def is_available(self) -> bool:
        """Return False because Puter STT is only available in the browser."""
        return False

    def get_model_name(self) -> str:
        """Return the configured Puter STT model label."""
        return self.model

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> TranscriptionResult:
        """Return a backend-unavailable result for browser-only Puter STT."""
        start = time.time()
        return TranscriptionResult(
            provider=self.provider_name,
            error=BACKEND_UNAVAILABLE_MESSAGE,
            latency_ms=(time.time() - start) * 1000,
        )
