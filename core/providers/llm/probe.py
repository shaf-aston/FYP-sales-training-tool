"""Probe LLM provider that echoes prompt payloads for experimentation."""

from __future__ import annotations

import json

from ..base import BaseLLMProvider, LLMResponse


class ProbeProvider(BaseLLMProvider):
    provider_name = "probe"

    def __init__(self, model: str | None = None):
        self.model = model or "probe-json"

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None) -> LLMResponse:
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
        return True

    def get_model_name(self) -> str:
        return self.model
