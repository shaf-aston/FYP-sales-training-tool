"""Deepgram speech-to-text provider."""

from __future__ import annotations

import json
import os
import time

from ..base import BaseSTTProvider, TranscriptionResult
from ..config import (
    DEFAULT_DEEPGRAM_BASE_URL,
    DEFAULT_DEEPGRAM_STT_MODEL,
    get_deepgram_api_key,
)
from ..http import ProviderHTTPError, post_bytes


class DeepgramSTTProvider(BaseSTTProvider):
    provider_name = "deepgram"
    _rate_limit_until = 0.0

    def __init__(self, model: str | None = None):
        """Initialise the Deepgram model, base URL, and API key."""
        self.model = model or os.environ.get("DEEPGRAM_STT_MODEL") or DEFAULT_DEEPGRAM_STT_MODEL
        self.base_url = (os.environ.get("DEEPGRAM_BASE_URL") or DEFAULT_DEEPGRAM_BASE_URL).rstrip("/")
        self.api_key = get_deepgram_api_key()

    @classmethod
    def _apply_rate_limit_cooldown(cls):
        """Pause future requests briefly after a rate limit response."""
        cls._rate_limit_until = time.time() + 60

    @classmethod
    def _is_rate_limited(cls) -> bool:
        """Return True while the temporary rate-limit cooldown is active."""
        return time.time() < cls._rate_limit_until

    def is_available(self) -> bool:
        """Return True when Deepgram is configured and not cooling down."""
        return bool(self.api_key) and not self._is_rate_limited()

    def get_model_name(self) -> str:
        """Return the active Deepgram STT model name."""
        return self.model

    @staticmethod
    def infer_content_type(filename: str | None) -> str:
        """Infer the upload content type from the audio filename."""
        if not filename:
            return "audio/webm"
        _, ext = os.path.splitext(filename.lower())
        return {
            ".webm": "audio/webm",
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".mp4": "audio/mp4",
            ".ogg": "audio/ogg",
        }.get(ext, "application/octet-stream")

    @staticmethod
    def _extract_transcript(body: dict) -> str:
        """Extract the primary transcript text from a Deepgram response body."""
        results = body.get("results") or {}
        channels = results.get("channels") or []
        if not channels:
            return ""
        alternatives = channels[0].get("alternatives") or []
        if not alternatives:
            return ""
        return (alternatives[0].get("transcript") or "").strip()

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> TranscriptionResult:
        """Send audio bytes to Deepgram and return the transcript result."""
        start = time.time()
        if not self.api_key:
            return TranscriptionResult(
                provider=self.provider_name,
                error="Deepgram API key is not configured.",
                latency_ms=(time.time() - start) * 1000,
            )

        if self._is_rate_limited():
            return TranscriptionResult(
                provider=self.provider_name,
                error="Deepgram rate limit cooldown active.",
                rate_limited=True,
                latency_ms=(time.time() - start) * 1000,
            )

        query = f"model={self.model}&smart_format=true"
        content_type = self.infer_content_type(filename)
        try:
            raw_body, _headers = post_bytes(
                f"{self.base_url}/listen?{query}",
                body=audio_bytes,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": content_type,
                },
            )
            body = json.loads(raw_body.decode("utf-8"))
            transcript = self._extract_transcript(body)
            return TranscriptionResult(
                text=transcript,
                provider=self.provider_name,
                latency_ms=(time.time() - start) * 1000,
            )
        except ProviderHTTPError as exc:
            if exc.status_code == 429:
                self._apply_rate_limit_cooldown()
                return TranscriptionResult(
                    provider=self.provider_name,
                    error=f"Deepgram HTTP 429: {exc.body or exc.reason}",
                    rate_limited=True,
                    latency_ms=(time.time() - start) * 1000,
                )
            return TranscriptionResult(
                provider=self.provider_name,
                error=f"Deepgram HTTP {exc.status_code}: {exc.body or exc.reason}",
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return TranscriptionResult(
                provider=self.provider_name,
                error=f"Deepgram request failed: {exc}",
                latency_ms=(time.time() - start) * 1000,
            )
