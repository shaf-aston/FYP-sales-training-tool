"""Groq chat provider."""

from __future__ import annotations

import logging
import time
from typing import Any, cast

from groq import Groq, APIConnectionError, RateLimitError, AuthenticationError

from ..base import ACCESS_DENIED, BaseLLMProvider, LLMResponse, RATE_LIMIT
from ..config import get_groq_api_keys, get_groq_llm_model

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    provider_name = "groq"

    def __init__(self, model: str | None = None):
        self.model = model or get_groq_llm_model()
        self.api_keys = get_groq_api_keys()
        groq_client = cast(Any, Groq)
        self.clients = [groq_client(api_key=key) for key in self.api_keys]

    def is_available(self) -> bool:
        return bool(self.api_keys)

    def get_model_name(self) -> str:
        return self.model

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None) -> LLMResponse:
        start = time.time()
        if not self.clients:
            return LLMResponse(
                error="Groq API keys are not configured.",
                latency_ms=(time.time() - start) * 1000,
            )

        last_error = "Groq request failed."
        last_error_code = None
        for client in self.clients:
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                message_content = response.choices[0].message.content or ""
                content = message_content.strip()
                return LLMResponse(
                    content=content,
                    latency_ms=(time.time() - start) * 1000,
                )
            except RateLimitError as exc:
                last_error = str(exc)
                last_error_code = RATE_LIMIT
                continue
            except AuthenticationError as exc:
                last_error = str(exc)
                return LLMResponse(
                    error=f"Groq authentication failed: {last_error}",
                    error_code=ACCESS_DENIED,
                    latency_ms=(time.time() - start) * 1000,
                )
            except APIConnectionError as exc:
                last_error = str(exc)
                return LLMResponse(
                    error=f"Groq connection error: {last_error}",
                    latency_ms=(time.time() - start) * 1000,
                )
            except Exception as exc:
                return LLMResponse(
                    error=f"Groq request failed: {exc}",
                    latency_ms=(time.time() - start) * 1000,
                )

        return LLMResponse(
            error=f"Groq rate limit reached: {last_error}",
            error_code=last_error_code,
            latency_ms=(time.time() - start) * 1000,
        )
