"""End-to-end test for the rate-limit fallback path in SalesChatbot.chat()."""

from chatbot.chatbot import SalesChatbot
from chatbot.providers import base as provider_base
from chatbot.providers.base import LLMResponse, RATE_LIMIT


class _StubProvider:
    """Minimal provider that returns a scripted LLMResponse per call."""

    def __init__(self, responses, model="stub-model", available=True):
        self._responses = list(responses)
        self._calls = 0
        self._model = model
        self._available = available

    def chat(self, messages, temperature=0.8, max_tokens=200, stage=None):
        resp = self._responses[min(self._calls, len(self._responses) - 1)]
        self._calls += 1
        return resp

    def is_available(self):
        return self._available

    def get_model_name(self):
        return self._model


def _rate_limited():
    return LLMResponse(
        content="",
        model="primary-model",
        latency_ms=12.0,
        error="429 rate_limit_exceeded",
        error_code=RATE_LIMIT,
    )


def _ok(content="fallback worked"):
    return LLMResponse(
        content=content,
        model="fallback-model",
        latency_ms=34.0,
        error=None,
        error_code=None,
    )


def test_rate_limit_triggers_fallback_and_swaps_provider(monkeypatch):
    """On RATE_LIMIT, chat() should switch to the next registered provider and return its reply."""

    bot = SalesChatbot(product_type="cars")

    primary = _StubProvider([_rate_limited()])
    fallback = _StubProvider([_ok("fallback worked")])

    bot.provider = primary
    bot._provider_name = "groq"
    bot._model_name = "primary-model"

    def fake_create_provider(name, model=None):
        if name == "groq":
            return primary
        return fallback

    monkeypatch.setattr("chatbot.chatbot.create_provider", fake_create_provider)
    monkeypatch.setattr(
        "chatbot.providers.factory._PROVIDERS",
        {"groq": object, "sambanova": object},
    )

    response = bot.chat("hi there")

    assert response.content == "fallback worked"
    assert response.provider != "groq"
    assert bot._provider_name != "groq"
    assert primary._calls == 1
    assert fallback._calls == 1


def test_rate_limit_without_error_code_still_detected_via_string(monkeypatch):
    """Providers that don't set error_code should still be caught by the string fallback."""

    bot = SalesChatbot(product_type="cars")

    legacy_rate_limit = LLMResponse(
        content="",
        model="primary-model",
        latency_ms=10.0,
        error="HTTP 429: Too Many Requests",
        error_code=None,
    )
    primary = _StubProvider([legacy_rate_limit])
    fallback = _StubProvider([_ok("picked up anyway")])

    bot.provider = primary
    bot._provider_name = "groq"

    monkeypatch.setattr(
        "chatbot.chatbot.create_provider",
        lambda name, model=None: fallback if name != "groq" else primary,
    )
    monkeypatch.setattr(
        "chatbot.providers.factory._PROVIDERS",
        {"groq": object, "sambanova": object},
    )

    response = bot.chat("hello")
    assert response.content == "picked up anyway"
    assert bot._provider_name != "groq"


def test_rate_limit_constant_still_exported():
    """Protects the RATE_LIMIT import path the rest of the codebase relies on."""
    assert provider_base.RATE_LIMIT == "RATE_LIMIT"
    resp = LLMResponse(
        content="", model="m", latency_ms=0, error="x", error_code=RATE_LIMIT
    )
    assert resp.error_code == RATE_LIMIT
