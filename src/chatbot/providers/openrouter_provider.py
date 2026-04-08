"""OpenRouter cloud provider - OpenAI compatible API"""

import os
import time
import logging
import threading
import requests
from typing import List, Dict

from .base import BaseLLMProvider, LLMResponse, auto_log_performance

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """Cloud LLM via OpenRouter API."""

    API_BASE = "https://openrouter.ai/api/v1"

    def __init__(self, model: str | None = None):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        # Default to an auto-switching model or a reliable free model if none specified
        self.model = model or os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        self._session = None
        self._session_lock = threading.Lock()

        logger.info(
            f"OpenRouterProvider initialized | Model: {self.model} | "
            f"Keys available: {1 if self.api_key else 0}"
        )

    @auto_log_performance
    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str | None = None) -> LLMResponse:
        if not self.is_available():
            error_msg = f"OpenRouter unavailable. API Key: {'Set' if self.api_key else 'Missing'}"
            logger.error(error_msg)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=error_msg)

        request_start_time = time.time()
        try:
            session = self._get_session()
            response = session.post(
                f"{self.API_BASE}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=30
            )
            response.raise_for_status()

            latency = (time.time() - request_start_time) * 1000
            data = response.json()

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=self.model,
                latency_ms=latency
            )

        except requests.exceptions.HTTPError as e:
            error_detail = e.response.json().get("error", {}).get("message", str(e)) if e.response is not None else str(e)
            logger.error(f"OpenRouter HTTP error: {error_detail}", exc_info=True)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=error_detail)
            
        except Exception as e:
            logger.error(f"OpenRouter API error: {str(e)}", exc_info=True)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=str(e))

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get_model_name(self) -> str:
        return self.model

    def _get_session(self):
        """Get or create thread-safe requests session with persistent headers."""
        with self._session_lock:
            if not self._session:
                self._session = requests.Session()
                self._session.headers.update({
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "FYP Sales Chatbot",
                    "Content-Type": "application/json"
                })
        return self._session
