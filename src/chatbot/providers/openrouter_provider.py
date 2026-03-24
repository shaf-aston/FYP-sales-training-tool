"""OpenRouter cloud provider - unified API for multiple LLM providers"""

import os
import time
import logging
import threading
import requests
from typing import List, Dict

from .base import BaseLLMProvider, LLMResponse, auto_log_performance

logger = logging.getLogger(__name__)


class OpenRouterProvider(BaseLLMProvider):
    """Cloud LLM via OpenRouter API with automatic fallback to backup key."""

    API_BASE = "https://openrouter.ai/api/v1"

    def __init__(self, model: str = None):
        # Try primary key, fallback to backup
        self.api_key = (
            os.environ.get("OPENROUTER_BACKUP_API_KEY", "").strip()
        )
        self.model = model or os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        # Handle openrouter/free alias
        if self.model == "openrouter/free":
            self.model = "meta-llama/llama-3.3-70b-instruct:free"
        self._session = None
        self._session_lock = threading.Lock()

        logger.info(
            f"OpenRouterProvider initialized | Model: {self.model} | "
            f"API Key: {'Present' if self.api_key else 'Missing'}"
        )

    @auto_log_performance
    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str = None) -> LLMResponse:
        if not self.is_available():
            error_msg = f"OpenRouter unavailable. API Key: {'Missing' if not self.api_key else 'Set'}"
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
            error_detail = e.response.json().get("error", {}).get("message", str(e)) if e.response else str(e)
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
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/your-repo",  # Optional: helps with analytics
                    "X-Title": "Sales Roleplay Chatbot"  # Optional: shows in OpenRouter dashboard
                })
        return self._session
