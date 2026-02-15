"""Provider factory - one-liner provider creation with automatic fallback"""
import os
from .base import BaseLLMProvider
from .groq_provider import GroqProvider
from .ollama_provider import OllamaProvider

# Provider constants (single source of truth)
GROQ = 'groq'
OLLAMA = 'ollama'

# Provider registry
PROVIDERS = {
    GROQ: GroqProvider,
    OLLAMA: OllamaProvider
}


def create_provider(provider_type: str = None, model: str = None) -> BaseLLMProvider:
    """Create provider instance with automatic fallback to env variable/default"""
    provider_type = (provider_type or os.environ.get("LLM_PROVIDER", "groq")).lower()
    
    if provider_type not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_type}. Available: {list(PROVIDERS.keys())}")
    
    return PROVIDERS[provider_type](model=model)


def get_available_providers() -> dict:
    """Check which providers are ready to use"""
    status = {}
    for name, cls in PROVIDERS.items():
        try:
            instance = cls()
            status[name] = {
                "available": instance.is_available(),
                "model": instance.get_model_name()
            }
        except Exception as e:
            status[name] = {"available": False, "error": str(e)}
    return status
