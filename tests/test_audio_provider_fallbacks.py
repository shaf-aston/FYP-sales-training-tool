"""Focused tests for STT/TTS fallback provider selection."""

from __future__ import annotations

from core.providers.stt.factory import create_stt_provider, list_stt_fallback_providers, list_stt_providers
from core.providers.tts.factory import create_tts_provider, list_tts_fallback_providers, list_tts_providers


def test_stt_provider_order_keeps_puter_as_backup(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER_ORDER", "groq,sambanova")

    assert list_stt_providers() == ["deepgram", "puter"]
    assert list_stt_fallback_providers("deepgram") == ["puter"]


def test_tts_provider_order_keeps_puter_as_backup(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER_ORDER", "groq,edge")

    assert list_tts_providers() == ["edge", "puter"]
    assert list_tts_fallback_providers("edge") == ["puter"]


def test_stt_falls_back_to_puter_when_primary_is_unavailable(monkeypatch):
    primary_cls = create_stt_provider("deepgram").__class__
    puter_cls = create_stt_provider("puter").__class__

    monkeypatch.setattr(primary_cls, "is_available", lambda self: False)
    monkeypatch.setattr(puter_cls, "is_available", lambda self: True)

    provider = create_stt_provider()

    assert provider.provider_name == "puter"
    assert provider.is_available() is True


def test_tts_falls_back_to_puter_when_primary_is_unavailable(monkeypatch):
    primary_cls = create_tts_provider("edge").__class__
    puter_cls = create_tts_provider("puter").__class__

    monkeypatch.setattr(primary_cls, "is_available", lambda self: False)
    monkeypatch.setattr(puter_cls, "is_available", lambda self: True)

    provider = create_tts_provider()

    assert provider.provider_name == "puter"
    assert provider.is_available() is True


def test_puter_adapters_stay_thin_and_explicit():
    stt_provider = create_stt_provider("puter")
    tts_provider = create_tts_provider("puter")

    assert stt_provider.is_available() is False
    assert stt_provider.transcribe(b"audio").error.startswith("Puter STT uses the browser SDK")
    assert tts_provider.is_available() is False
    assert tts_provider.synthesize("hello").error.startswith("Puter TTS uses the browser SDK")
