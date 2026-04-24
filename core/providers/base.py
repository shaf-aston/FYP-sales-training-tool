"""Shared provider contracts and response models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

RATE_LIMIT = "rate_limit"
ACCESS_DENIED = "access_denied"


@dataclass
class LLMResponse:
    content: str = ""
    latency_ms: float = 0.0
    error: str | None = None
    error_code: str | None = None


@dataclass
class TranscriptionResult:
    text: str = ""
    latency_ms: float = 0.0
    provider: str = ""
    error: str | None = None
    rate_limited: bool = False
    fallback_recommended: str | None = None


@dataclass
class SynthesisResult:
    audio_bytes: bytes = b""
    content_type: str = "audio/wav"
    latency_ms: float = 0.0
    provider: str = ""
    voice: str = ""
    error: str | None = None
    fallback_recommended: str | None = None


class BaseLLMProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_model_name(self) -> str:
        raise NotImplementedError


class BaseSTTProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> TranscriptionResult:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_model_name(self) -> str:
        raise NotImplementedError


class BaseTTSProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def synthesize(self, text: str, voice: str = "male_us", rate: int = 0) -> SynthesisResult:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_model_name(self) -> str:
        raise NotImplementedError
