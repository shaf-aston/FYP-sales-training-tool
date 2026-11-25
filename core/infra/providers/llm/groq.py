"""Groq chat provider."""

from __future__ import annotations

import logging
from typing import Any, cast

from groq import APIConnectionError, AuthenticationError, BadRequestError, Groq, NotFoundError, RateLimitError

from core.infra.constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, GROQ_BACKUP_MODELS, GROQ_REASONING_EFFORT, PROVIDER_ATTEMPTS, PROVIDER_TIMEOUT_SECONDS
from core.infra.providers.base import BaseLLMProvider, LLMResponse
from core.infra.providers.config import get_groq_api_keys, get_groq_llm_model

logger = logging.getLogger(__name__)
_GONE = ("model_not_found", "model_decommissioned", "does not exist", "decommissioned")


def _model_gone(exc: Exception) -> bool:
    """Groq retired or doesn't know the model (a 404, or a 400 naming it decommissioned)."""
    return isinstance(exc, NotFoundError) or (isinstance(exc, BadRequestError)
                                              and any(k in str(exc).lower() for k in _GONE))


class GroqProvider(BaseLLMProvider):
    provider_name = "groq"

    def __init__(self, model: str | None = None):
        """Initialise the Groq client pool and chosen model name."""
        self.model = model or get_groq_llm_model()
        self.api_keys = get_groq_api_keys()
        groq_client = cast(Any, Groq)
        self.clients = [
            groq_client(api_key=key, timeout=PROVIDER_TIMEOUT_SECONDS, max_retries=PROVIDER_ATTEMPTS - 1)
            for key in self.api_keys
        ]

    def is_available(self) -> bool:
        """Return True when at least one Groq API key is configured."""
        return bool(self.api_keys)

    def get_model_name(self) -> str:
        """Return the active Groq model name."""
        return self.model

    def chat(self, messages, temperature=DEFAULT_TEMPERATURE, max_tokens=DEFAULT_MAX_TOKENS) -> LLMResponse:
        """Send the chat request to Groq; a rate-limited key passes the request to the next key. When Groq says
        the model is gone, the next backup model (limits.yaml groq_backup_models) takes over for good."""
        if not self.clients:
            return LLMResponse(error="Groq API keys are not configured.")
        tried = set()
        while True:
            response, gone = self._chat_once(messages, temperature, max_tokens)
            tried.add(self.model)
            backup = next((m for m in GROQ_BACKUP_MODELS if m not in tried), None)
            if not gone or backup is None:
                return response
            logger.error("groq model %s is gone (%s); switching to %s", self.model, response.error, backup)
            self.model = backup

    def _chat_once(self, messages, temperature, max_tokens) -> tuple[LLMResponse, bool]:
        """One try with the current model: (response, whether the model itself is gone)."""

        # extra_body: works with any SDK version on the server, old ones lack the keyword
        extra = {"extra_body": {"reasoning_effort": GROQ_REASONING_EFFORT[self.model]}} if self.model in GROQ_REASONING_EFFORT else {}
        last_error = "Groq request failed."
        for client in self.clients:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **extra,
                )
                return LLMResponse(content=(response.choices[0].message.content or "").strip()), False
            except RateLimitError as exc:
                last_error = str(exc)
                continue
            except AuthenticationError as exc:
                return LLMResponse(error=f"Groq authentication failed: {exc}"), False
            except APIConnectionError as exc:
                return LLMResponse(error=f"Groq connection error: {exc}"), False
            except Exception as exc:
                return LLMResponse(error=f"Groq request failed: {exc}"), _model_gone(exc)

        return LLMResponse(error=f"Groq rate limit reached: {last_error}"), False
