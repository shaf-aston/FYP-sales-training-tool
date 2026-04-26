"""Factory helpers for STT providers."""

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
from ..config import DEFAULT_STT_PROVIDER_ORDER, get_stt_provider_order
from .deepgram import DeepgramSTTProvider

STT_PROVIDER_TYPES = {
    "deepgram": DeepgramSTTProvider,
}


@lru_cache(maxsize=1)
def _load_puter_provider():
    module_path = Path(__file__).with_name("puter-stt.py")
    module = load_module_from_path(
        "core.providers.stt.puter_fallback",
        str(module_path),
    )
    provider_cls = getattr(module, "PuterSTTProvider", None)
    if provider_cls is None:
        raise ImportError(f"{module_path.name} does not define PuterSTTProvider")
    STT_PROVIDER_TYPES["puter"] = provider_cls
    return provider_cls


def _provider_registry() -> dict[str, type]:
    _load_puter_provider()
    return STT_PROVIDER_TYPES


def supported_stt_provider_names() -> list[str]:
    return list_stt_providers()


def list_stt_providers() -> list[str]:
    return ordered_provider_names(
        get_stt_provider_order(),
        DEFAULT_STT_PROVIDER_ORDER,
        _provider_registry(),
    )


def list_stt_fallback_providers(current_provider: str | None = None) -> list[str]:
    return fallback_provider_names(list_stt_providers(), current_provider)


def create_stt_provider(provider_type: str | None = None, model: str | None = None):
    return create_audio_provider(
        _provider_registry(),
        list_stt_providers(),
        provider_type=provider_type,
        model=model,
    )


def get_available_stt_providers() -> list[dict[str, object]]:
    return available_provider_metadata(_provider_registry(), list_stt_providers())
