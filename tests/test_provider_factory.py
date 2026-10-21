import pytest

from core.providers.factory import create_provider, list_providers
from core.providers.llm import GroqProvider


def test_create_provider_accepts_aliases_and_rejects_unknown_names():
    assert isinstance(create_provider(" GroqCloud "), GroqProvider)
    with pytest.raises(ValueError, match="Unknown provider"):
        create_provider("nope")


def test_list_providers_keeps_config_order_without_duplicates_or_unknowns(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "groq,bogus,groq,sambanova")

    assert list_providers() == ["groq"]


def test_a_thinking_model_is_told_not_to_think_so_short_calls_are_not_empty(monkeypatch):
    sent = {}

    class Done:
        choices = [type("C", (), {"message": type("M", (), {"content": "ok"})()})()]

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    sent.update(kw)
                    return Done()

    p = GroqProvider(model="qwen/qwen3.8-27b")
    p.clients = [Client()]
    assert p.chat([{"role": "user", "content": "hi"}], max_tokens=30).content == "ok"
    assert sent["extra_body"] == {"reasoning_effort": "none"}
    sent.clear()
    p.model = "some/other-model"  # a model that doesn't know the setting must never get it
    p.chat([{"role": "user", "content": "hi"}], max_tokens=30)
    assert "extra_body" not in sent
