"""Shared provider contracts and response models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    content: str = ""
    error: str | None = None


class BaseLLMProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def chat(self, messages, temperature, max_tokens) -> LLMResponse:
        """Send a chat request and return the provider response wrapper."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the provider is configured and ready to use."""
        raise NotImplementedError

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier currently used by this provider."""
        raise NotImplementedError
