"""Abstract base class for LLM providers"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""
    content: str
    model: str
    latency_ms: float
    error: Optional[str] = None
    stage: Optional[str] = None  # Track stage context for logging


def auto_log_performance(chat_method):
    """Decorator: Automatically logs LLM performance without cluttering business logic"""
    @wraps(chat_method)
    def wrapper(self, *args, **kwargs):
        response = chat_method(self, *args, **kwargs)
        
        # Auto-log in background
        stage = kwargs.get('stage', 'unknown')
        logger.info(f"LLM Response | Model: {response.model} | Latency: {response.latency_ms:.0f}ms | Stage: {stage}")
        
        if response.error:
            logger.error(f"LLM Error: {response.error}")
        
        return response
    return wrapper


class BaseLLMProvider(ABC):
    """Contract: All LLM providers must implement these methods"""
    
    @abstractmethod
    @auto_log_performance
    def chat(self, messages: List[Dict], temperature: float = 0.8, max_tokens: int = 200, stage: str = None) -> LLMResponse:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        pass
