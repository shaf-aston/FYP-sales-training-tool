"""Buy mode's coach answers the learner's questions about the live call."""
from types import SimpleNamespace

from core import coach
from core.enums import Stage
from core.services.provider_router import ProviderRouter


def _router(monkeypatch, *providers):
    """A real router over stub providers; the first one is the active provider."""
    by_name = {p.provider_name: p for p in providers}
    monkeypatch.setattr("core.services.provider_router.create_provider", lambda name: by_name[name])
    monkeypatch.setattr(
        "core.services.provider_router.list_providers", lambda fallback=False: list(by_name)
    )
    return ProviderRouter(providers[0].provider_name)


class _RecordingProvider:
    def __init__(self, content="What is stopping them?"):
        self.content = content
        self.calls = []
        self.provider_name = "groq"

    def is_available(self):
        return True

    def get_model_name(self):
        return self.provider_name

    def chat(self, messages, temperature, max_tokens):
        self.calls.append(messages)
        return SimpleNamespace(content=self.content, error=None)


class _Call:
    current_stage = Stage.LOGICAL
    strategy = "consultative"
    conversation_history = [
        {"role": "user", "content": "I need more clarity"},
        {"role": "assistant", "content": "What matters most here"},
    ]


def test_socratic_answer_keeps_question_marks(monkeypatch):
    provider = _RecordingProvider(content="What is the real gap? Why now?")

    result = coach.answer_question(_router(monkeypatch, provider), _Call(), "What should I do next", style="socratic")

    assert result == {"answer": "What is the real gap? Why now?"}
    system_prompt = provider.calls[0][0]["content"]
    assert "stage: logical" in system_prompt and "Stage." not in system_prompt
    assert "CUSTOMER: I need more clarity" in system_prompt


def test_tactical_answer_keeps_original_punctuation(monkeypatch):
    provider = _RecordingProvider(content="Ask them what hurts most?")

    result = coach.answer_question(_router(monkeypatch, provider), _Call(), "What should I do next", style="tactical")

    assert result == {"answer": "Ask them what hurts most?"}
