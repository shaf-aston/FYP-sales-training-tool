"""Provider registry: one constructor and one ordered name list."""

from __future__ import annotations

from .config import DEFAULT_LLM_PROVIDER_ORDER, get_llm_fallback_order, get_llm_provider_order
from .llm import GroqProvider

LLM_PROVIDER_TYPES = {
    "groq": GroqProvider,
}

_PROVIDER_ALIASES = {
    "groqcloud": "groq",
}


def create_provider(name: str, model: str | None = None):
    """Build the named provider. Unknown names raise ValueError."""
    key = name.strip().lower()
    key = _PROVIDER_ALIASES.get(key, key)
    if key not in LLM_PROVIDER_TYPES:
        supported = ", ".join(sorted(LLM_PROVIDER_TYPES))
        raise ValueError(f"Unknown provider '{key}'. Supported providers: {supported}")
    return LLM_PROVIDER_TYPES[key](model=model)


def list_providers(fallback: bool = False) -> list[str]:
    """Return known providers in configured order, then any defaults the config left out."""
    configured = get_llm_fallback_order() if fallback else get_llm_provider_order()
    names = [*configured, *DEFAULT_LLM_PROVIDER_ORDER]
    return list(dict.fromkeys(n for n in names if n in LLM_PROVIDER_TYPES))


def get_available_providers():
    """Return basic availability metadata for each known provider."""
    providers = []
    for name in list_providers():
        provider = create_provider(name)
        providers.append(
            {
                "name": name,
                "available": provider.is_available(),
                "model": provider.get_model_name(),
            }
        )
    return providers
