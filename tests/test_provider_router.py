"""One fallback path for every caller: advisor chatbot and prospect buyer alike."""

import pytest

from core.providers.base import LLMResponse
from core.services.provider_router import ProviderRouter


class _Provider:
    def __init__(self, name, reply="", error=None, available=True):
        self.provider_name, self.reply, self.error, self.available = name, reply, error, available

    def is_available(self):
        return self.available

    def get_model_name(self):
        return f"{self.provider_name}-model"

    def chat(self, messages, temperature=0.8, max_tokens=200):  # no `stage`, like test stubs
        return LLMResponse(content=self.reply, error=self.error)


@pytest.fixture
def router(monkeypatch):
    providers = {
        "groq": _Provider("groq", error="429 rate_limit_exceeded"),
        "down": _Provider("down", available=False),
        "empty": _Provider("empty", reply="   "),
        "good": _Provider("good", reply="hi there"),
    }
    monkeypatch.setattr(
        "core.services.provider_router.list_providers", lambda fallback=False: list(providers)
    )
    monkeypatch.setattr(
        "core.services.provider_router.create_provider", lambda name, model=None: providers[name]
    )
    return ProviderRouter()


def test_skips_unavailable_and_empty_then_switches_to_first_good(router):
    result = router.chat_with_fallback([], temperature=0.5, max_tokens=80)
    assert result.ok and result.response.content == "hi there"
    assert (router.provider_name, router.model_name) == ("good", "good-model")


def test_all_fail_returns_first_error_and_keeps_provider(router, monkeypatch):
    monkeypatch.setattr("core.services.provider_router.list_providers", lambda fallback=False: ["groq"])
    result = router.chat_with_fallback([])
    assert not result.ok and "429" in result.response.error
    assert router.provider_name == "groq"
