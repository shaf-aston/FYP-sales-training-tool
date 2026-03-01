"""Ollama local LLM provider - runs models on local hardware"""
import os
import time
import requests
from typing import List, Dict
from .base import BaseLLMProvider, LLMResponse, auto_log_performance


class OllamaProvider(BaseLLMProvider):
    """Local LLM via Ollama - zero cloud dependency, complete privacy"""

    # Ollama API endpoints
    CHAT_ENDPOINT = "/api/chat"
    TAGS_ENDPOINT = "/api/tags"

    DEFAULT_MODEL = "phi3:mini"  # 3.8B params, best speed/quality for dev

    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or os.environ.get("OLLAMA_MODEL", self.DEFAULT_MODEL)
        self.base_url = base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self._available_cache = None  # (bool, timestamp)
        self._cache_ttl = 30  # seconds

    @auto_log_performance
    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str = None) -> LLMResponse:
        if not self.is_available():
            return LLMResponse(content="", model=self.model, latency_ms=0, error="Ollama server not running or model not installed")

        request_start_time = time.time()
        try:
            ollama_response = requests.post(
                f"{self.base_url}{self.CHAT_ENDPOINT}",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": min(max_tokens, 300),
                        "num_ctx": 4096,
                        "top_p": 0.9,
                        "top_k": 40,
                        "repeat_penalty": 1.1
                    }
                },
                timeout=60
            )
            ollama_response.raise_for_status()
            request_latency_ms = (time.time() - request_start_time) * 1000

            return LLMResponse(
                content=ollama_response.json().get("message", {}).get("content", ""),
                model=self.model,
                latency_ms=request_latency_ms
            )
        except requests.exceptions.ConnectionError:
            return LLMResponse(content="", model=self.model, latency_ms=0, error="Connection failed - start Ollama with 'ollama serve'")
        except requests.exceptions.Timeout:
            return LLMResponse(content="", model=self.model, latency_ms=0, error="Request timed out - Ollama may be overloaded")
        except requests.exceptions.HTTPError as e:
            return LLMResponse(content="", model=self.model, latency_ms=0, error=f"HTTP error from Ollama: {e.response.status_code}")
        except Exception as e:
            return LLMResponse(content="", model=self.model, latency_ms=0, error=str(e))

    def is_available(self) -> bool:
        """Check if Ollama server is running and required model is installed.

        Results are cached for _cache_ttl seconds to avoid redundant network calls.
        """
        # Return cached result if fresh
        if self._available_cache:
            cached_result, cached_time = self._available_cache
            if time.time() - cached_time < self._cache_ttl:
                return cached_result

        try:
            response = requests.get(f"{self.base_url}{self.TAGS_ENDPOINT}", timeout=2)
            if response.status_code != 200:
                self._available_cache = (False, time.time())
                return False

            models = response.json().get("models", [])
            model_family = self.model.split(":")[0]

            result = any(model_family in m["name"] for m in models)
            self._available_cache = (result, time.time())
            return result
        except requests.exceptions.RequestException:
            self._available_cache = (False, time.time())
            return False

    def get_model_name(self) -> str:
        return self.model
