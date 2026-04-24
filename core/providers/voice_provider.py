"""Voice provider facade for the Deepgram STT and Edge TTS pipeline."""

from __future__ import annotations

from .base import SynthesisResult, TranscriptionResult
from .config import get_stt_provider_order, get_tts_provider_order
from .stt import DeepgramSTTProvider
from .tts import EdgeTTSProvider, GroqTTSProvider

DEFAULT_VOICE_MAP = {
    "male_us": "male_us",
    "female_us": "female_us",
}

STT_PROVIDER_TYPES = {
    "deepgram": DeepgramSTTProvider,
}

TTS_PROVIDER_TYPES = {
    "groq": GroqTTSProvider,
    "edge": EdgeTTSProvider,
}


class VoiceProvider:
    """Coordinates STT and TTS providers without leaking provider specifics to routes."""

    def __init__(self):
        self._stt_order = self._resolve_order(get_stt_provider_order(), STT_PROVIDER_TYPES)
        self._tts_order = self._resolve_order(get_tts_provider_order(), TTS_PROVIDER_TYPES)

    @staticmethod
    def _resolve_order(configured: list[str], registry: dict[str, type]) -> list[str]:
        seen = set()
        ordered = []
        for name in configured:
            if name in registry and name not in seen:
                ordered.append(name)
                seen.add(name)
        for fallback in registry:
            if fallback not in seen:
                ordered.append(fallback)
        return ordered

    def _build_stt_provider(self, provider_name: str):
        return STT_PROVIDER_TYPES[provider_name]()

    def _build_tts_provider(self, provider_name: str):
        return TTS_PROVIDER_TYPES[provider_name]()

    def is_stt_available(self) -> bool:
        return any(self._build_stt_provider(name).is_available() for name in self._stt_order)

    def is_tts_available(self) -> bool:
        return any(self._build_tts_provider(name).is_available() for name in self._tts_order)

    def get_available_voices(self):
        return DEFAULT_VOICE_MAP.copy()

    def get_status(self):
        return {
            "stt_provider": self._stt_order[0] if self._stt_order else "",
            "tts_provider": self._tts_order[0] if self._tts_order else "",
            "stt_available": self.is_stt_available(),
            "tts_available": self.is_tts_available(),
            "stt_fallback_order": self._stt_order,
            "tts_fallback_order": self._tts_order,
        }

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm"):
        last_result = TranscriptionResult(
            provider=self._stt_order[0] if self._stt_order else "stt",
            error="No STT providers configured or available.",
        )
        for provider_name in self._stt_order:
            provider = self._build_stt_provider(provider_name)
            if not provider.is_available():
                continue
            result = provider.transcribe(audio_bytes, filename=filename)
            result.provider = getattr(provider, "provider_name", provider_name)
            if not result.error and result.text:
                return result
            last_result = result

        return last_result

    def synthesize(self, text: str, voice: str = "male_us", rate: int = 0):
        last_result = SynthesisResult(
            provider=self._tts_order[0] if self._tts_order else "tts",
            voice=voice,
            error="No TTS providers configured or available.",
        )
        for provider_name in self._tts_order:
            provider = self._build_tts_provider(provider_name)
            if not provider.is_available():
                continue
            result = provider.synthesize(text, voice=voice, rate=rate)
            result.provider = getattr(provider, "provider_name", provider_name)
            if not result.error and result.audio_bytes:
                return result
            last_result = result

        return last_result
