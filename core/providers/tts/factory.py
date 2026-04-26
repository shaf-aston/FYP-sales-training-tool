"""Factory helpers for TTS providers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .._audio_provider_utils import (
    available_provider_metadata,
    create_audio_provider,
    fallback_provider_names,
    ordered_provider_names,
)
from .._module_loader import load_module_from_path
from ..config import DEFAULT_TTS_PROVIDER_ORDER, get_tts_provider_order
from .edge import EdgeTTSProvider

TTS_PROVIDER_TYPES = {
    "edge": EdgeTTSProvider,
}


@lru_cache(maxsize=1)
def _load_puter_provider():
    module_path = Path(__file__).with_name("puter-tts.py")
    module = load_module_from_path(
        "core.providers.tts.puter_fallback",
        str(module_path),
    )
    provider_cls = getattr(module, "PuterTTSProvider", None)
    if provider_cls is None:
        raise ImportError(f"{module_path.name} does not define PuterTTSProvider")
    TTS_PROVIDER_TYPES["puter"] = provider_cls
    return provider_cls


def _provider_registry() -> dict[str, type]:
    _load_puter_provider()
    return TTS_PROVIDER_TYPES


def supported_tts_provider_names() -> list[str]:
    return list_tts_providers()


def list_tts_providers() -> list[str]:
    return ordered_provider_names(
        get_tts_provider_order(),
        DEFAULT_TTS_PROVIDER_ORDER,
        _provider_registry(),
    )


def list_tts_fallback_providers(current_provider: str | None = None) -> list[str]:
    return fallback_provider_names(list_tts_providers(), current_provider)


def create_tts_provider(provider_type: str | None = None, model: str | None = None):
    return create_audio_provider(
        _provider_registry(),
        list_tts_providers(),
        provider_type=provider_type,
        model=model,
    )


def get_available_tts_providers() -> list[dict[str, object]]:
    return available_provider_metadata(_provider_registry(), list_tts_providers())
