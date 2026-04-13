"""Probe provider for experiments — echoes the assembled messages

Useful for deterministic experiments that inspect the exact `system` prompt
and message payload sent to the provider without calling an external API
"""

from typing import Dict, List, Optional
import json
from .base import BaseLLMProvider, LLMResponse


class ProbeProvider(BaseLLMProvider):
    """Echoes the messages payload as the response content (JSON string)

    The output is intentionally deterministic to allow exact comparisons
    between prompt variants in experiments
    """

    def __init__(self, model: Optional[str] = None):
        self._model = model or "probe-model"

    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str | None = None) -> LLMResponse:
        # Create a readable dump: include the first system prompt and then the messages list
        system = next((m for m in messages if m.get("role") == "system"), {})
        dump = {
            "system_prompt": system.get("content", ""),
            "messages": messages,
            "stage": stage,
        }
        content = json.dumps(dump, ensure_ascii=False)
        return LLMResponse(content=content, model=self._model, latency_ms=0.0)

    def is_available(self) -> bool:
        return True

    def get_model_name(self) -> str:
        return self._model
