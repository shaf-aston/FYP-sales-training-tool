"""Probe LLM provider that echoes prompt payloads for experimentation."""

from __future__ import annotations

import json

from ..base import BaseLLMProvider, LLMResponse


class ProbeProvider(BaseLLMProvider):
    provider_name = "probe"

    def __init__(self, model: str | None = None):
        """Initialise the probe provider used to inspect payloads in tests."""
        self.model = model or "probe-json"

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None) -> LLMResponse:
        """Return the request payload as JSON instead of calling a real model."""
        return LLMResponse(
            content=json.dumps(
                {
                    "message_count": len(messages or []),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stage": str(stage) if stage is not None else None,
                    "messages": messages,
                }
            )
        )

    def is_available(self) -> bool:
        """Return True because the probe provider has no external dependency."""
        return True

    def get_model_name(self) -> str:
        """Return the probe provider label."""
        return self.model
