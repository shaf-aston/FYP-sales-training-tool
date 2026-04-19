"""Groq cloud provider."""

import importlib.util
import logging
import os
import threading
import time
from typing import Any, Dict, List

from .base import (
    BaseLLMProvider,
    LLMResponse,
    auto_log_performance,
    error_response,
    RATE_LIMIT,
    UNAVAILABLE,
    PROVIDER_ERROR,
)

logger = logging.getLogger(__name__)

Groq: Any = None
GROQ_AVAILABLE = importlib.util.find_spec("groq") is not None
if GROQ_AVAILABLE:
    from groq import Groq


class GroqProvider(BaseLLMProvider):
    """Cloud LLM via Groq API with automatic key rotation on rate limit."""

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        # Build list of available API keys for rotation
        self._api_keys = [
            k
            for k in [
                os.environ.get("SAFE_GROQ_API_KEY", "").strip(),
                os.environ.get("ALTERNATIVE_GROQ_API_KEY", "").strip(),
            ]
            if k
        ]
        self.api_key = self._api_keys[0] if self._api_keys else ""
        self._current_key_index = 0
        self._client = None
        self._client_lock = threading.Lock()
        logger.info(
            f"GroqProvider initialized with model: {self.model}, API keys available: {len(self._api_keys)}"
        )

    @auto_log_performance
    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.8,
        max_tokens: int = 200,
        stage: str | None = None,
    ) -> LLMResponse:
        if not self.is_available():
            return error_response(
                self.model,
                f"Groq unavailable. Library: {GROQ_AVAILABLE}, API Key: {'Set' if self.api_key else 'Missing'}",
                UNAVAILABLE,
            )

        request_start_time = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=25,
            )
            latency = (time.time() - request_start_time) * 1000
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=self.model,
                latency_ms=latency,
            )

        except Exception as e:
            error_str = str(e).lower()
            # On rate limit, try rotating to next Groq API key before giving up
            if ("rate_limit" in error_str or "429" in error_str) and len(self._api_keys) > 1:
                return self._retry_with_next_key(messages, temperature, max_tokens, request_start_time)

            err_code = RATE_LIMIT if ("rate_limit" in error_str or "429" in error_str) else PROVIDER_ERROR
            logger.error(f"Groq API error: {str(e)}", exc_info=True)
            return error_response(self.model, str(e), err_code)

    def _retry_with_next_key(self, messages: List[Dict], temperature: float, max_tokens: int, request_start_time: float) -> LLMResponse:
        """Retry chat with next API key after rate limit."""
        next_index = (self._current_key_index + 1) % len(self._api_keys)
        if next_index == self._current_key_index:
            return error_response(self.model, "No alternative API keys available", RATE_LIMIT)

        logger.warning(f"Groq rate limit on key {self._current_key_index + 1}, rotating to key {next_index + 1}")
        self._current_key_index = next_index
        self.api_key = self._api_keys[next_index]
        with self._client_lock:
            self._client = Groq(api_key=self.api_key)

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=25,
            )
            latency = (time.time() - request_start_time) * 1000
            return LLMResponse(content=response.choices[0].message.content or "", model=self.model, latency_ms=latency)
        except Exception as retry_e:
            err_code = RATE_LIMIT if ("rate_limit" in str(retry_e).lower() or "429" in str(retry_e)) else PROVIDER_ERROR
            logger.error(f"Groq retry also failed: {retry_e}")
            return error_response(self.model, str(retry_e), err_code)

    def is_available(self) -> bool:
        return GROQ_AVAILABLE and bool(self.api_key)

    def get_model_name(self) -> str:
        return self.model

    def _get_client(self):
        with self._client_lock:
            if not self._client:
                self._client = Groq(api_key=self.api_key)
        return self._client
