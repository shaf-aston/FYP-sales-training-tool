"""Provider factories for env-driven LLM selection and fallbacks."""

from __future__ import annotations

from dataclasses import dataclass

from .config import get_llm_fallback_order, get_llm_provider_order
from .llm import DummyProvider, GroqProvider, ProbeProvider, SambaNovaProvider

LLM_PROVIDER_TYPES = {
    "dummy": DummyProvider,
    "groq": GroqProvider,
    "probe": ProbeProvider,
    "sambanova": SambaNovaProvider,
}
NON_PRODUCTION_PROVIDER_TYPES = {"dummy", "probe"}

_PROVIDER_ALIASES = {
    "samba": "sambanova",
    "samba-nova": "sambanova",
    "samba_nova": "sambanova",
    "groqcloud": "groq",
}


@dataclass(frozen=True)
class ProviderResolution:
    selected: str
    reason: str
    checked: list[dict]
    requested: str | None = None
    configured_order: list[str] | None = None


def normalize_provider_name(raw_name: str | None) -> str | None:
    name = (raw_name or "").strip().lower()
    if not name:
        return None
    return _PROVIDER_ALIASES.get(name, name)


def supported_provider_names(include_non_production: bool = True) -> list[str]:
    return list_providers(include_non_production=include_non_production)


def _ordered_provider_names(
    configured_names: list[str], *, include_non_production: bool
) -> list[str]:
    seen = set()
    ordered = []
    for provider_name in configured_names:
        if provider_name not in LLM_PROVIDER_TYPES or provider_name in seen:
            continue
        if (
            not include_non_production
            and provider_name in NON_PRODUCTION_PROVIDER_TYPES
        ):
            continue
        seen.add(provider_name)
        ordered.append(provider_name)

    defaults = (
        ("groq", "sambanova", "dummy", "probe")
        if include_non_production
        else ("groq", "sambanova")
    )
    for provider_name in defaults:
        if provider_name not in seen:
            ordered.append(provider_name)
    return ordered


def list_providers(include_non_production: bool = True) -> list[str]:
    return _ordered_provider_names(
        get_llm_provider_order(),
        include_non_production=include_non_production,
    )


def list_runtime_providers() -> list[str]:
    """Return providers eligible for automatic chat selection."""
    return list_providers(include_non_production=False)


def list_fallback_providers(current_provider: str | None = None) -> list[str]:
    """Return ordered real-provider fallbacks for chat retries."""
    current = (current_provider or "").strip().lower()
    return [
        provider_name
        for provider_name in _ordered_provider_names(
            get_llm_fallback_order(),
            include_non_production=False,
        )
        if provider_name != current
    ]


def get_available_providers():
    providers = []
    for provider_name in list_providers():
        provider = create_provider(provider_name)
        providers.append(
            {
                "name": provider_name,
                "available": provider.is_available(),
                "model": provider.get_model_name(),
            }
        )
    return providers


def resolve_provider(
    provider_type: str | None = None, *, model: str | None = None
) -> ProviderResolution:
    """Resolve which provider should be used, returning a trace for debugging."""
    requested = normalize_provider_name(provider_type)
    if requested:
        if requested not in LLM_PROVIDER_TYPES:
            supported = ", ".join(sorted(LLM_PROVIDER_TYPES.keys()))
            raise ValueError(
                f"Unknown provider '{requested}'. Supported providers: {supported}"
            )
        return ProviderResolution(
            selected=requested,
            reason="requested",
            checked=[{"name": requested, "available": None}],
            requested=requested,
            configured_order=get_llm_provider_order(),
        )

    checked: list[dict] = []
    configured_order = list_runtime_providers()
    for provider_name in configured_order:
        provider = create_provider(provider_name, model=model)
        available = bool(provider.is_available())
        checked.append({"name": provider_name, "available": available})
        if available:
            return ProviderResolution(
                selected=provider_name,
                reason="first_available",
                checked=checked,
                requested=None,
                configured_order=configured_order,
            )

    # If nothing is available, fall back deterministically to the first configured runtime provider.
    preferred_provider = configured_order[0]
    checked.append({"name": preferred_provider, "available": False, "fallback": True})
    return ProviderResolution(
        selected=preferred_provider,
        reason="none_available_fallback",
        checked=checked,
        requested=None,
        configured_order=configured_order,
    )


def create_provider_with_trace(provider_type: str | None = None, model: str | None = None):
    trace = resolve_provider(provider_type, model=model)
    provider = create_provider(trace.selected, model=model)
    return provider, trace


def create_provider(provider_type=None, model=None):
    requested = normalize_provider_name(provider_type)
    if requested:
        if requested not in LLM_PROVIDER_TYPES:
            supported = ", ".join(sorted(LLM_PROVIDER_TYPES.keys()))
            raise ValueError(
                f"Unknown provider '{requested}'. Supported providers: {supported}"
            )
        provider_cls = LLM_PROVIDER_TYPES[requested]
        return provider_cls(model=model) if requested in ("groq", "sambanova") else provider_cls()

    # Auto-select: first available provider in runtime order
    resolution = resolve_provider(None, model=model)
    return create_provider(resolution.selected, model=model)
