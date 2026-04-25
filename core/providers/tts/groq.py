"""Groq text-to-speech provider."""

from __future__ import annotations

import json
import os
import time

from ..base import BaseTTSProvider, SynthesisResult
from ..config import (
    DEFAULT_GROQ_BASE_URL,
    DEFAULT_GROQ_TTS_FORMAT,
    DEFAULT_GROQ_TTS_MODEL,
    DEFAULT_GROQ_TTS_VOICE,
    get_voice_groq_api_keys,
)
from ..http import ProviderHTTPError, post_bytes


class GroqTTSProvider(BaseTTSProvider):
    provider_name = "groq"

    def __init__(self, model: str | None = None, voice: str | None = None, fmt: str | None = None):
        self.model = model or os.environ.get("GROQ_TTS_MODEL") or DEFAULT_GROQ_TTS_MODEL
        self.voice = voice or os.environ.get("GROQ_TTS_VOICE") or DEFAULT_GROQ_TTS_VOICE
        self.format = fmt or os.environ.get("GROQ_TTS_FORMAT") or DEFAULT_GROQ_TTS_FORMAT
        self.base_url = (os.environ.get("GROQ_BASE_URL") or DEFAULT_GROQ_BASE_URL).rstrip("/")
        self.api_keys = get_voice_groq_api_keys()

    def is_available(self) -> bool:
        return bool(self.api_keys)

    def get_model_name(self) -> str:
        return self.model

    def synthesize(self, text: str, voice: str = "male_us", rate: int = 0) -> SynthesisResult:
        start = time.time()
        if not self.api_keys:
            return SynthesisResult(
                provider=self.provider_name,
                voice=voice,
                error="Groq voice API keys are not configured.",
                latency_ms=(time.time() - start) * 1000,
            )

        payload = {
            "model": self.model,
            "voice": self.voice,
            "input": text,
            "response_format": self.format,
        }
        body = json.dumps(payload).encode("utf-8")
        last_error = "Groq TTS failed."

        for api_key in self.api_keys:
            try:
                audio_bytes, headers = post_bytes(
                    f"{self.base_url}/audio/speech",
                    body=body,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=45,
                )
                content_type = headers.get("Content-Type") or "audio/wav"
                return SynthesisResult(
                    provider=self.provider_name,
                    voice=voice,
                    audio_bytes=audio_bytes,
                    content_type=content_type,
                    latency_ms=(time.time() - start) * 1000,
                )
            except ProviderHTTPError as exc:
                last_error = exc.body or exc.reason
                if exc.status_code == 429:
                    continue
                return SynthesisResult(
                    provider=self.provider_name,
                    voice=voice,
                    error=f"Groq HTTP {exc.status_code}: {last_error}",
                    latency_ms=(time.time() - start) * 1000,
                )
            except Exception as exc:
                return SynthesisResult(
                    provider=self.provider_name,
                    voice=voice,
                    error=f"Groq request failed: {exc}",
                    latency_ms=(time.time() - start) * 1000,
                )

        return SynthesisResult(
            provider=self.provider_name,
            voice=voice,
            error=f"Groq rate limit reached: {last_error}",
            latency_ms=(time.time() - start) * 1000,
        )
