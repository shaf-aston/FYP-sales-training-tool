"""TTS provider implementations."""

from .edge import EdgeTTSProvider
from .factory import (
    create_tts_provider,
    get_available_tts_providers,
    list_tts_fallback_providers,
    list_tts_providers,
    supported_tts_provider_names,
)

__all__ = [
    "EdgeTTSProvider",
    "create_tts_provider",
    "get_available_tts_providers",
    "list_tts_fallback_providers",
    "list_tts_providers",
    "supported_tts_provider_names",
]
