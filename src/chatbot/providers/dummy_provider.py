"""Deterministic test provider — never calls external APIs."""

from typing import List, Dict, Optional
from .base import BaseLLMProvider, LLMResponse


class DummyProvider(BaseLLMProvider):
    """Deterministic test provider used in tests (no external calls)."""

    def __init__(self, model: Optional[str] = None):
        self._model = model or "dummy-model"

    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.8,
        max_tokens: int = 200,
        stage: str | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content="I understand — tell me more.",
            model=self._model,
            latency_ms=1.0,
        )

    def is_available(self) -> bool:
        return True

    def get_model_name(self) -> str:
        return self._model
