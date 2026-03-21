"""Ollama local LLM provider — runs models on local hardware, zero cloud dependency."""

import logging
import os
import time

import requests
from typing import List, Dict

from .base import BaseLLMProvider, LLMResponse, auto_log_performance

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Local LLM via Ollama. Configure with OLLAMA_MODEL and OLLAMA_HOST env vars."""

    CHAT_ENDPOINT = "/api/chat"
    TAGS_ENDPOINT = "/api/tags"
    DEFAULT_MODEL = "llama3.2:3b"

    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or self.DEFAULT_MODEL
        self.base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._available_cache = None
        self._cache_ttl = 30
        logger.info(f"OllamaProvider initialized: model={self.model}, host={self.base_url}")

    @auto_log_performance
    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str = None) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(
                content="", model=self.model, latency_ms=0,
                error=f"Ollama not available. Run: ollama pull {self.model} && ollama serve",
            )

        start = time.time()
        try:
            resp = requests.post(
                f"{self.base_url}{self.CHAT_ENDPOINT}",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        "num_ctx": int(os.environ.get("OLLAMA_NUM_CTX", 4096)),
                        "top_p": float(os.environ.get("OLLAMA_TOP_P", 0.9)),
                        "top_k": int(os.environ.get("OLLAMA_TOP_K", 40)),
                        "repeat_penalty": float(os.environ.get("OLLAMA_REPEAT_PENALTY", 1.1)),
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            latency_ms = (time.time() - start) * 1000
            return LLMResponse(
                content=resp.json().get("message", {}).get("content", ""),
                model=self.model,
                latency_ms=latency_ms,
            )
        except requests.exceptions.ConnectionError:
            return LLMResponse(content="", model=self.model, latency_ms=0,
                               error="Connection failed — start Ollama with 'ollama serve'")
        except requests.exceptions.Timeout:
            return LLMResponse(content="", model=self.model, latency_ms=0,
                               error="Request timed out — model may be loading or overloaded")
        except requests.exceptions.HTTPError as e:
            return LLMResponse(content="", model=self.model, latency_ms=0,
                               error=f"HTTP {e.response.status_code} from Ollama")
        except Exception as e:
            return LLMResponse(content="", model=self.model, latency_ms=0, error=str(e))

    def is_available(self) -> bool:
        """Check if Ollama server is running and model is installed. Cached for 30s."""
        if self._available_cache is not None:
            cached_result, cached_time = self._available_cache
            if time.time() - cached_time < self._cache_ttl:
                return cached_result

        try:
            resp = requests.get(f"{self.base_url}{self.TAGS_ENDPOINT}", timeout=2)
            if resp.status_code != 200:
                self._available_cache = (False, time.time())
                return False

            models = resp.json().get("models", [])
            model_family = self.model.split(":")[0]
            result = any(m["name"] == self.model or m["name"].startswith(model_family + ":") for m in models)
            self._available_cache = (result, time.time())
            return result
        except requests.exceptions.RequestException:
            self._available_cache = (False, time.time())
            return False

    def get_model_name(self) -> str:
        return self.model
