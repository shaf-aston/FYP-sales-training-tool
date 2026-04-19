"""Abstract base class for LLM providers"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import wraps
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# Canonical Error Codes
RATE_LIMIT = "RATE_LIMIT"
UNAVAILABLE = "UNAVAILABLE"
TIMEOUT = "TIMEOUT"
AUTH_ERROR = "AUTH_ERROR"
PROVIDER_ERROR = "PROVIDER_ERROR"


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""

    content: str
    model: str
    latency_ms: float
    error: Optional[str] = None
    error_code: Optional[str] = None


def auto_log_performance(chat_method):
    """Decorator: log LLM latency and errors after each chat() call."""

    @wraps(chat_method)
    def wrapper(self, *args, **kwargs):
        start = time.time()
        response = chat_method(self, *args, **kwargs)
        if response.latency_ms == 0:
            response.latency_ms = (time.time() - start) * 1000
        stage = kwargs.get("stage", "unknown")
        logger.info(
            f"LLM Response | Model: {response.model} | Latency: {response.latency_ms:.0f}ms | Stage: {stage}"
        )
        if response.error:
            logger.error(f"LLM Error: {response.error}")
        return response

    return wrapper


def map_http_status_to_error_code(status_code: int) -> str:
    """Map HTTP status code to canonical error code."""
    if status_code == 429:
        return RATE_LIMIT
    elif status_code in (401, 403):
        return AUTH_ERROR
    elif status_code >= 500:
        return UNAVAILABLE
    else:
        return PROVIDER_ERROR


def error_response(model: str, error_msg: str, error_code: str) -> LLMResponse:
    """Create standardised error response."""
    return LLMResponse(content="", model=model, latency_ms=0, error=error_msg, error_code=error_code)


class BaseLLMProvider(ABC):
    """Contract: All LLM providers must implement these methods"""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.8,
        max_tokens: int = 200,
        stage: str | None = None,
    ) -> LLMResponse:
        """Generate response from LLM. Implementations should use @auto_log_performance."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        pass
