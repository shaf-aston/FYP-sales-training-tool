"""Groq cloud provider - wraps existing Groq API integration"""

import os
import time
import logging
import threading
import importlib.util
from typing import List, Dict

from .base import BaseLLMProvider, LLMResponse, auto_log_performance

logger = logging.getLogger(__name__)

GROQ_AVAILABLE = importlib.util.find_spec("groq") is not None
if GROQ_AVAILABLE:
    from groq import Groq


class GroqProvider(BaseLLMProvider):
    """Cloud LLM via Groq API with automatic key rotation on rate limit."""

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        # Build list of available API keys for rotation
        self._api_keys = [
            k for k in [
                os.environ.get("SAFE_GROQ_API_KEY", "").strip(),
                os.environ.get("ALTERNATIVE_GROQ_API_KEY", "").strip(),
            ] if k
        ]
        self.api_key = self._api_keys[0] if self._api_keys else ""
        self._current_key_index = 0
        self._client = None
        self._client_lock = threading.Lock()
        logger.info(f"GroqProvider initialized with model: {self.model}, API keys available: {len(self._api_keys)}")

    @auto_log_performance
    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str | None = None) -> LLMResponse:
        if not self.is_available():
            error_msg = f"Groq unavailable. Library: {GROQ_AVAILABLE}, API Key: {'Set' if self.api_key else 'Missing'}"
            logger.error(error_msg)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=error_msg)

        request_start_time = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=25,
            )
            latency = (time.time() - request_start_time) * 1000
            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=self.model,
                latency_ms=latency
            )

        except Exception as e:
            error_str = str(e)
            # On rate limit, try rotating to the next Groq API key before giving up
            if ("rate_limit" in error_str.lower() or "429" in error_str) and len(self._api_keys) > 1:
                next_index = (self._current_key_index + 1) % len(self._api_keys)
                if next_index != self._current_key_index:
                    logger.warning(f"Groq rate limit on key {self._current_key_index + 1}, rotating to key {next_index + 1}")
                    self._current_key_index = next_index
                    self.api_key = self._api_keys[next_index]
                    with self._client_lock:
                        self._client = Groq(api_key=self.api_key)
                    # Retry once with the new key
                    try:
                        response = self._client.chat.completions.create(
                            model=self.model,
                            messages=messages,  # type: ignore[arg-type]
                            temperature=temperature,
                            max_tokens=max_tokens,
                            timeout=25,
                        )
                        latency = (time.time() - request_start_time) * 1000
                        return LLMResponse(
                            content=response.choices[0].message.content or "",
                            model=self.model,
                            latency_ms=latency
                        )
                    except Exception as retry_e:
                        logger.error(f"Groq retry also failed: {retry_e}")
                        return LLMResponse(content="", model=self.model, latency_ms=0, error=str(retry_e))

            logger.error(f"Groq API error: {error_str}", exc_info=True)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=error_str)

    def is_available(self) -> bool:
        return GROQ_AVAILABLE and bool(self.api_key)

    def get_model_name(self) -> str:
        return self.model

    def _get_client(self):
        with self._client_lock:
            if not self._client:
                self._client = Groq(api_key=self.api_key)
        return self._client
