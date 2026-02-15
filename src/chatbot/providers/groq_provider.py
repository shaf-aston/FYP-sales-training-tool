"""Groq cloud provider - wraps existing Groq API integration"""
import os
import time
from typing import List, Dict
from .base import BaseLLMProvider, LLMResponse
import requests
import logging

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import lru_cache
from ..performance import PerformanceTracker
from ..config import get_groq_model

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


class GroqProvider(BaseLLMProvider):
    """Cloud LLM via Groq API with persistent client."""

    def __init__(self, model: str = None):
        # Fetch the model from the centralized configuration
        self.model = model or get_groq_model()
        self.api_key = os.environ.get("SAFE_GROQ_API_KEY", "").strip()
        self._client = None  # Instance variable, not class variable
        logger.info(f"GroqProvider initialized with model: {self.model}, API key present: {bool(self.api_key)}")

    def _get_client(self):
        if not self._client:
            self._client = Groq(api_key=self.api_key)
        return self._client

    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str = None) -> LLMResponse:
        if not self.is_available():
            error_msg = f"Groq unavailable. Library: {GROQ_AVAILABLE}, API Key: {'Set' if self.api_key else 'Missing'}"
            logger.error(error_msg)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=error_msg)
        
        request_start_time = time.time()
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            latency = (time.time() - request_start_time) * 1000
            return LLMResponse(
                content=response.choices[0].message.content,
                model=self.model,
                latency_ms=latency
            )

        except Exception as e:
            logger.error(f"Groq API error: {str(e)}", exc_info=True)
            return LLMResponse(content="", model=self.model, latency_ms=0, error=str(e))

    def is_available(self) -> bool:
        return GROQ_AVAILABLE and self.api_key is not None
    
    def get_model_name(self) -> str:
        return self.model
