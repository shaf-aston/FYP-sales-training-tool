"""Tests for training coach scoring and feedback generation."""
from types import SimpleNamespace

from core import trainer
from core.utils import Stage, Strategy


class _DummyProvider:
    def __init__(self, content="What is stopping them?", error=False):
        self.content = content
        self.error = error
        self.calls = []

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
