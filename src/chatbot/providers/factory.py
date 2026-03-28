"""Provider factory - one-liner provider creation with automatic fallback"""
from .base import BaseLLMProvider
from .groq_provider import GroqProvider
from .openrouter_provider import OpenRouterProvider
from .sambanova_provider import SambaNovaProvider
from .dummy_provider import DummyProvider

# Provider registry
PROVIDERS = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "sambanova": SambaNovaProvider,
    "dummy": DummyProvider,
}

def create_provider(provider_type: str = None, model: str = None) -> BaseLLMProvider:
    """Create provider instance with automatic fallback to env variable/default"""
    provider_type = (provider_type or "groq").lower()
    
    if provider_type not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_type}. Available: {list(PROVIDERS.keys())}")
    
    return PROVIDERS[provider_type](model=model)


_cached_instances: dict[str, BaseLLMProvider] = {}


def get_available_providers() -> dict:
    """Check which providers are ready to use (instances cached to avoid repeated init)."""
    status = {}
    for name, cls in PROVIDERS.items():
        try:
            if name not in _cached_instances:
                _cached_instances[name] = cls()
            instance = _cached_instances[name]
            status[name] = {
                "available": instance.is_available(),
                "model": instance.get_model_name()
            }
        except Exception as e:
            status[name] = {"available": False, "error": str(e)}
    return status
