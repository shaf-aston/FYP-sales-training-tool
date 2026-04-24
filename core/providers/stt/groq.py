"""Groq speech-to-text provider."""

from __future__ import annotations

import json
import os
import time

from ..base import BaseSTTProvider, TranscriptionResult
from ..config import (
    DEFAULT_GROQ_BASE_URL,
    DEFAULT_GROQ_STT_MODEL,
    get_voice_groq_api_keys,
)
from ..http import ProviderHTTPError, post_multipart

CONTENT_TYPE_BY_EXT = {
    ".webm": "audio/webm",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".ogg": "audio/ogg",
}


class GroqSTTProvider(BaseSTTProvider):
    provider_name = "groq"

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GROQ_STT_MODEL") or DEFAULT_GROQ_STT_MODEL
        self.base_url = (os.environ.get("GROQ_BASE_URL") or DEFAULT_GROQ_BASE_URL).rstrip("/")
        self.api_keys = get_voice_groq_api_keys()

    def is_available(self) -> bool:
        return bool(self.api_keys)

    def get_model_name(self) -> str:
        return self.model

    @staticmethod
    def infer_content_type(filename: str | None) -> str:
        if not filename:
            return "audio/webm"
        _, ext = os.path.splitext(filename.lower())
        return CONTENT_TYPE_BY_EXT.get(ext, "application/octet-stream")

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> TranscriptionResult:
        start = time.time()
        if not self.api_keys:
            return TranscriptionResult(
                provider=self.provider_name,
                error="Groq API keys are not configured.",
                latency_ms=(time.time() - start) * 1000,
            )

        fields = {
            "model": self.model,
            "response_format": "json",
        }
        content_type = self.infer_content_type(filename)
        last_error = "Groq transcription failed."

        for api_key in self.api_keys:
            try:
                raw_body, _headers = post_multipart(
                    f"{self.base_url}/audio/transcriptions",
                    fields=fields,
                    file_field="file",
                    filename=filename,
                    content_type=content_type,
                    file_bytes=audio_bytes,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                body = json.loads(raw_body.decode("utf-8"))
                return TranscriptionResult(
                    text=(body.get("text") or "").strip(),
                    provider=self.provider_name,
                    latency_ms=(time.time() - start) * 1000,
                )
            except ProviderHTTPError as exc:
                last_error = exc.body or exc.reason
                if exc.status_code == 429:
                    continue
                return TranscriptionResult(
                    provider=self.provider_name,
                    error=f"Groq HTTP {exc.status_code}: {last_error}",
                    latency_ms=(time.time() - start) * 1000,
                )
            except Exception as exc:
                return TranscriptionResult(
                    provider=self.provider_name,
                    error=f"Groq request failed: {exc}",
                    latency_ms=(time.time() - start) * 1000,
                )

        return TranscriptionResult(
            provider=self.provider_name,
            error=f"Groq rate limit reached: {last_error}",
            rate_limited=True,
            latency_ms=(time.time() - start) * 1000,
        )
