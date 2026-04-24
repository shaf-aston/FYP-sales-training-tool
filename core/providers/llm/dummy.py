"""Deterministic dummy LLM provider for tests and offline flows."""

from __future__ import annotations

from ..base import BaseLLMProvider, LLMResponse


class DummyProvider(BaseLLMProvider):
    provider_name = "dummy"

    def __init__(self, model: str | None = None):
        self.model = model or "dummy-fixed-response"

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None) -> LLMResponse:
        return LLMResponse(content="Dummy provider response.")

    def is_available(self) -> bool:
        return True

    def get_model_name(self) -> str:
        return self.model
