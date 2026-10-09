"""Groq chat provider."""

from __future__ import annotations

import logging
from typing import Any, cast

from groq import Groq, APIConnectionError, RateLimitError, AuthenticationError

from ...constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from ..base import BaseLLMProvider, LLMResponse
from ..config import get_groq_api_keys, get_groq_llm_model

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    provider_name = "groq"

    def __init__(self, model: str | None = None):
        """Initialise the Groq client pool and chosen model name."""
        self.model = model or get_groq_llm_model()
        self.api_keys = get_groq_api_keys()
        groq_client = cast(Any, Groq)
        self.clients = [groq_client(api_key=key) for key in self.api_keys]

    def is_available(self) -> bool:
        """Return True when at least one Groq API key is configured."""
        return bool(self.api_keys)

    def get_model_name(self) -> str:
        """Return the active Groq model name."""
        return self.model

    def chat(self, messages, temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS) -> LLMResponse:
        """Send the chat request to Groq; a rate-limited key passes the request to the next key."""
        if not self.clients:
            return LLMResponse(error="Groq API keys are not configured.")

        last_error = "Groq request failed."
        for client in self.clients:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return LLMResponse(content=(response.choices[0].message.content or "").strip())
            except RateLimitError as exc:
                last_error = str(exc)
                continue
            except AuthenticationError as exc:
                return LLMResponse(error=f"Groq authentication failed: {exc}")
            except APIConnectionError as exc:
                return LLMResponse(error=f"Groq connection error: {exc}")
            except Exception as exc:
                return LLMResponse(error=f"Groq request failed: {exc}")

        return LLMResponse(error=f"Groq rate limit reached: {last_error}")
