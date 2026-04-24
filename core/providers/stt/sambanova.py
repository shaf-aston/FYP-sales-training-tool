"""SambaNova speech-to-text provider."""

from __future__ import annotations

import json
import os
import time

from ..base import BaseSTTProvider, TranscriptionResult
from ..config import (
    DEFAULT_SAMBANOVA_BASE_URL,
    DEFAULT_SAMBANOVA_STT_MODEL,
    get_sambanova_api_key,
)
from ..http import ProviderHTTPError, post_multipart
from .groq import CONTENT_TYPE_BY_EXT


class SambaNovaSTTProvider(BaseSTTProvider):
    provider_name = "sambanova"

    def __init__(self, model: str | None = None):
        self.model = (
            model or os.environ.get("SAMBANOVA_STT_MODEL") or DEFAULT_SAMBANOVA_STT_MODEL
        )
        self.base_url = (
            os.environ.get("SAMBANOVA_BASE_URL") or DEFAULT_SAMBANOVA_BASE_URL
        ).rstrip("/")
        self.api_key = get_sambanova_api_key()

    def is_available(self) -> bool:
        return bool(self.api_key)

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
        if not self.api_key:
            return TranscriptionResult(
                provider=self.provider_name,
                error="SambaNova API key is not configured.",
                latency_ms=(time.time() - start) * 1000,
            )

        try:
            raw_body, _headers = post_multipart(
                f"{self.base_url}/audio/transcriptions",
                fields={
                    "model": self.model,
                    "response_format": "json",
                },
                file_field="file",
                filename=filename,
                content_type=self.infer_content_type(filename),
                file_bytes=audio_bytes,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            body = json.loads(raw_body.decode("utf-8"))
            return TranscriptionResult(
                text=(body.get("text") or "").strip(),
                provider=self.provider_name,
                latency_ms=(time.time() - start) * 1000,
            )
        except ProviderHTTPError as exc:
            return TranscriptionResult(
                provider=self.provider_name,
                error=f"SambaNova HTTP {exc.status_code}: {exc.body or exc.reason}",
                rate_limited=exc.status_code == 429,
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return TranscriptionResult(
                provider=self.provider_name,
                error=f"SambaNova request failed: {exc}",
                latency_ms=(time.time() - start) * 1000,
            )
