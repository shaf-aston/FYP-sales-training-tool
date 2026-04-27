"""SambaNova chat provider."""

from __future__ import annotations

import json
import os
import time

from ..base import BaseLLMProvider, LLMResponse, RATE_LIMIT
from ..config import (
    DEFAULT_SAMBANOVA_BASE_URL,
    DEFAULT_SAMBANOVA_MODEL,
    get_sambanova_api_key,
)
from ..http import ProviderHTTPError, post_json


class SambaNovaProvider(BaseLLMProvider):
    provider_name = "sambanova"

    def __init__(self, model: str | None = None):
        """Initialise the SambaNova model name, base URL, and API key."""
        self.model = model or os.environ.get("SAMBANOVA_MODEL") or DEFAULT_SAMBANOVA_MODEL
        self.base_url = (
            os.environ.get("SAMBANOVA_BASE_URL") or DEFAULT_SAMBANOVA_BASE_URL
        ).rstrip("/")
        self.api_key = get_sambanova_api_key()

    def is_available(self) -> bool:
        """Return True when a SambaNova API key is configured."""
        return bool(self.api_key)

    def get_model_name(self) -> str:
        """Return the active SambaNova model name."""
        return self.model

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None) -> LLMResponse:
        """Send one chat completion request to the SambaNova HTTP API."""
        start = time.time()
        if not self.api_key:
            return LLMResponse(
                error="SambaNova API key is not configured.",
                latency_ms=(time.time() - start) * 1000,
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            raw_body, _headers = post_json(
                f"{self.base_url}/chat/completions",
                payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            body = json.loads(raw_body.decode("utf-8"))
            content = (
                body.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return LLMResponse(
                content=content,
                latency_ms=(time.time() - start) * 1000,
            )
        except ProviderHTTPError as exc:
            return LLMResponse(
                error=f"SambaNova HTTP {exc.status_code}: {exc.body or exc.reason}",
                error_code=RATE_LIMIT if exc.status_code == 429 else None,
                latency_ms=(time.time() - start) * 1000,
            )
        except Exception as exc:
            return LLMResponse(
                error=f"SambaNova request failed: {exc}",
                latency_ms=(time.time() - start) * 1000,
            )
