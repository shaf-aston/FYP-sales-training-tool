"""Provider factory. Picks the right LLM backend at runtime."""

from .base import BaseLLMProvider
from .dummy_provider import DummyProvider
from .groq_provider import GroqProvider
from .sambanova_provider import SambaNovaProvider
from .probe_provider import ProbeProvider

_PROVIDERS = {
    "groq": GroqProvider,
    "sambanova": SambaNovaProvider,
    "dummy": DummyProvider,
    "probe": ProbeProvider,
}


def create_provider(
    provider_type: str | None = None, model: str | None = None
) -> BaseLLMProvider:
    """Create provider instance with automatic fallback to env variable/default"""
    provider_type = (provider_type or "groq").lower()

    if provider_type not in _PROVIDERS:
        raise ValueError(
            f"Unknown provider: {provider_type}. Available: {list(_PROVIDERS.keys())}"
        )

    return _PROVIDERS[provider_type](model=model)


_cached_instances: dict[str, BaseLLMProvider] = {}


def list_providers() -> list[str]:
    """Registered provider names — stable across process lifetime."""
    return list(_PROVIDERS.keys())


def _get_providers_registry() -> dict:
    """Legacy test hook; prefer list_providers()."""
    return _PROVIDERS


def get_available_providers() -> dict:
    """Check which providers are available. Instances are cached on first call."""
    status = {}
    for name, cls in _PROVIDERS.items():
        try:
            if name not in _cached_instances:
                _cached_instances[name] = cls()
            instance = _cached_instances[name]
            status[name] = {
                "available": instance.is_available(),
                "model": instance.get_model_name(),
            }
        except Exception as e:
            status[name] = {"available": False, "error": str(e)}
    return status
