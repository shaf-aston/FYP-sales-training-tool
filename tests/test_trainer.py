"""Tests for the training coach answers."""
from types import SimpleNamespace

from core import trainer
from core.services.provider_router import ProviderRouter
from core.enums import Stage


def _router(monkeypatch, *providers):
    """A real router over stub providers; the first one is the active provider."""
    by_name = {p.provider_name: p for p in providers}
    monkeypatch.setattr(
        "core.services.provider_router.create_provider", lambda name, model=None: by_name[name]
    )
    monkeypatch.setattr(
        "core.services.provider_router.list_providers", lambda fallback=False: list(by_name)
    )
    return ProviderRouter(providers[0].provider_name)


class _DummyProvider:
    def __init__(self, content="What is stopping them?", error=False):
        self.content = content
        self.error = error
        self.calls = []
        self.provider_name = "groq"

    def is_available(self):
        return True

    def get_model_name(self):
        return self.provider_name

    def chat(self, messages, temperature, max_tokens, stage):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stage": stage,
            }
        )
        return SimpleNamespace(content=self.content, error=self.error)


class _DummyFlowEngine:
    current_stage = Stage.LOGICAL
    flow_type = "consultative"
    conversation_history = [
        {"role": "user", "content": "I need more clarity"},
        {"role": "assistant", "content": "What matters most here"},
    ]


def test_socratic_training_answer_preserves_question_marks(monkeypatch):
    provider = _DummyProvider(content="What is the real gap? Why now?")

    result = trainer.answer_training_question(
        _router(monkeypatch, provider),
        _DummyFlowEngine(),
        "What should I do next",
        style="socratic",
    )

    assert result == {"answer": "What is the real gap? Why now?"}
    assert provider.calls[0]["stage"] == Stage.LOGICAL


def test_tactical_training_answer_keeps_original_punctuation(monkeypatch):
    provider = _DummyProvider(content="Ask them what hurts most?")

    result = trainer.answer_training_question(
        _router(monkeypatch, provider),
        _DummyFlowEngine(),
        "What should I do next",
        style="tactical",
    )

    assert result == {"answer": "Ask them what hurts most?"}
