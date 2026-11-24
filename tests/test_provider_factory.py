import pytest

from core.infra.providers.factory import create_provider, list_providers
from core.infra.providers.llm import GroqProvider


def test_create_provider_normalizes_name_and_rejects_unknown_names():
    assert isinstance(create_provider(" Groq "), GroqProvider)  # case and surrounding spaces ignored
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


# --- a retired Groq model: the backup takes over instead of every reply going blank ---

def _groq_with(monkeypatch, behaviour, backups):
    import httpx
    from groq import NotFoundError
    from core.infra.providers.llm import groq as g

    asked = []

    class Completions:
        def create(self, model, **kw):
            asked.append(model)
            if behaviour(model) == "gone":
                req = httpx.Request("POST", "https://api.groq.com")
                raise NotFoundError("model_not_found", response=httpx.Response(404, request=req), body=None)
            if behaviour(model) == "boom":
                raise RuntimeError("server error")

            class R:
                choices = [type("C", (), {"message": type("M", (), {"content": f"hi from {model}"})()})()]
            return R()

    class Client:
        def __init__(self, **kw):
            self.chat = type("Chat", (), {"completions": Completions()})()

    monkeypatch.setattr(g, "Groq", Client)
    monkeypatch.setattr(g, "GROQ_BACKUP_MODELS", backups)
    monkeypatch.setattr(g, "get_groq_api_keys", lambda: ["k"])
    return g.GroqProvider(model="main"), asked


def test_a_gone_model_switches_to_the_backup_and_stays_there(monkeypatch):
    p, asked = _groq_with(monkeypatch, lambda m: "gone" if m == "main" else "ok", ["backup"])
    assert p.chat([{"role": "user", "content": "x"}]).content == "hi from backup"
    assert p.chat([{"role": "user", "content": "x"}]).content == "hi from backup"
    assert asked == ["main", "backup", "backup"] and p.get_model_name() == "backup"


def test_every_backup_gone_returns_the_error_without_looping(monkeypatch):
    p, asked = _groq_with(monkeypatch, lambda m: "gone", ["b1", "b2"])
    assert p.chat([{"role": "user", "content": "x"}]).error
    assert asked == ["main", "b1", "b2"]


def test_other_failures_and_no_backups_change_nothing(monkeypatch):
    p, asked = _groq_with(monkeypatch, lambda m: "boom", ["backup"])
    assert p.chat([{"role": "user", "content": "x"}]).error and asked == ["main"]
    p, asked = _groq_with(monkeypatch, lambda m: "gone", [])
    assert p.chat([{"role": "user", "content": "x"}]).error and asked == ["main"]
