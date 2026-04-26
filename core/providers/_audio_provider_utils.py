"""Shared selection helpers for STT and TTS provider factories."""

from __future__ import annotations

from typing import Any


def normalize_provider_name(raw_name: str | None) -> str | None:
    if raw_name is None:
        return None
    cleaned = raw_name.strip().lower()
    return cleaned or None


def ordered_provider_names(
    configured_names: list[str],
    default_names: list[str],
    registry: dict[str, type[Any]],
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    for provider_name in configured_names + default_names:
        normalized_name = normalize_provider_name(provider_name)
        if not normalized_name or normalized_name in seen:
            continue
        if normalized_name not in registry:
            continue
        seen.add(normalized_name)
        ordered.append(normalized_name)

    return ordered


def fallback_provider_names(
    ordered_names: list[str],
    current_provider: str | None = None,
) -> list[str]:
    current_name = normalize_provider_name(current_provider)
    return [name for name in ordered_names if name != current_name]


def create_audio_provider(
    registry: dict[str, type[Any]],
    ordered_names: list[str],
    provider_type: str | None = None,
    model: str | None = None,
):
    requested_name = normalize_provider_name(provider_type)

    if requested_name:
        provider_cls = registry.get(requested_name)
        if provider_cls is None:
            supported = ", ".join(sorted(registry))
            raise ValueError(
                f"Unknown provider '{requested_name}'. Supported providers: {supported}"
            )
        return provider_cls(model=model)

    for provider_name in ordered_names:
        provider = registry[provider_name](model=model)
        if provider.is_available():
            return provider

    return registry[ordered_names[0]](model=model)


def available_provider_metadata(
    registry: dict[str, type[Any]],
    ordered_names: list[str],
) -> list[dict[str, Any]]:
    providers = []
    for provider_name in ordered_names:
        provider = registry[provider_name]()
        providers.append(
            {
                "name": provider_name,
                "available": provider.is_available(),
                "model": provider.get_model_name(),
            }
        )
    return providers
