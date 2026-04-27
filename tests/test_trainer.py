"""Tests for training coach scoring and feedback generation."""
from types import SimpleNamespace

from core import trainer
from core.utils import Stage, Strategy


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
    flow_type = Strategy.CONSULTATIVE
    conversation_history = [
        {"role": "user", "content": "I need more clarity"},
        {"role": "assistant", "content": "What matters most here"},
    ]


def test_socratic_training_answer_preserves_question_marks():
    provider = _DummyProvider(content="What is the real gap? Why now?")

    result = trainer.answer_training_question(
        provider,
        _DummyFlowEngine(),
        "What should I do next",
        style="socratic",
    )

    assert result == {"answer": "What is the real gap? Why now?"}
    assert provider.calls[0]["stage"] == Stage.LOGICAL


def test_tactical_training_answer_keeps_original_punctuation():
    provider = _DummyProvider(content="Ask them what hurts most?")

    result = trainer.answer_training_question(
        provider,
        _DummyFlowEngine(),
        "What should I do next",
        style="tactical",
    )

    assert result == {"answer": "Ask them what hurts most?"}


def test_generate_training_uses_fallback_provider_when_primary_fails(monkeypatch):
    primary = _DummyProvider(content="", error=True)
    fallback = _DummyProvider(
        content=(
            '{"what_happened": "Asked a clear question", '
            '"next_move": "Probe the blocker", '
            '"watch_for": ["Over-probing", "Pitching too early"]}'
        ),
        error=False,
    )
    fallback.provider_name = "sambanova"

    monkeypatch.setattr(trainer, "list_fallback_providers", lambda current: ["sambanova"])
    monkeypatch.setattr(
        trainer,
        "create_provider",
        lambda name: fallback if name == "sambanova" else primary,
    )

    flow_engine = _DummyFlowEngine()

    result = trainer.generate_training(primary, flow_engine, "Need help", "Sure")

    assert primary.calls
    assert fallback.calls
    assert result["what_happened"] == "Asked a clear question"
    assert result["next_move"] == "Probe the blocker"
    assert result["watch_for"] == ["Over-probing", "Pitching too early"]
