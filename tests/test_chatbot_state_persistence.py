import logging
from pathlib import Path
from typing import Any, cast

from core.chatbot import SalesChatbot
from core.providers.base import LLMResponse
from core.prospect_session_persistence import ProspectSessionPersistence
from core.session_persistence import SessionPersistence


class _FakeFlowEngine:
    def __init__(self):
        self.flow_type = "intent"
        self.current_stage = "intent"
        self.stage_turn_count = 0
        self.initial_flow_type = "intent"
        self.conversation_history = []
        self.restored = None
        self.reset_calls = 0
        self.added_turns = []

    def reset_to_initial(self):
        self.reset_calls += 1
        self.flow_type = "intent"
        self.current_stage = "intent"
        self.stage_turn_count = 0
        self.initial_flow_type = "intent"

    def restore_state(self, snapshot):
        self.restored = snapshot
        self.flow_type = snapshot["flow_type"]
        self.current_stage = snapshot["current_stage"]
        self.stage_turn_count = snapshot["stage_turn_count"]
        self.initial_flow_type = snapshot["initial_flow_type"]

    def add_turn(self, user_message, bot_message):
        self.added_turns.append((user_message, bot_message))
        self.conversation_history.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": bot_message},
            ]
        )


def _build_bot() -> Any:
    bot = cast(Any, SalesChatbot.__new__(SalesChatbot))
    bot.flow_engine = _FakeFlowEngine()
    bot._turn_snapshots = []
    bot.session_id = "session123"
    bot.product_type = "default"
    bot.provider_type = "probe"
    bot.logger = logging.getLogger("test-chatbot")
    return bot


def test_rewind_to_zero_turn_resets_state_and_clears_snapshots(monkeypatch):
    bot = _build_bot()
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    bot._turn_snapshots = [{"current_stage": "logical"}]
    saved = []
    monkeypatch.setattr(bot, "save_session", lambda: saved.append(True))

    assert bot.rewind_to_turn(0) is True
    assert bot.flow_engine.conversation_history == []
    assert bot.flow_engine.reset_calls == 1
    assert bot._turn_snapshots == []
    assert saved == [True]


def test_rewind_to_turn_restores_snapshot_when_available(monkeypatch):
    bot = _build_bot()
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]
    bot._turn_snapshots = [
        {
            "flow_type": "consultative",
            "current_stage": "logical",
            "stage_turn_count": 1,
            "initial_flow_type": "consultative",
        },
        {
            "flow_type": "consultative",
            "current_stage": "pitch",
            "stage_turn_count": 2,
            "initial_flow_type": "consultative",
        },
    ]
    monkeypatch.setattr(bot, "save_session", lambda: None)

    assert bot.rewind_to_turn(1) is True
    assert bot.flow_engine.conversation_history == [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    assert bot.flow_engine.restored == bot._turn_snapshots[0]
    assert len(bot._turn_snapshots) == 1


def test_replay_calls_apply_advancement_for_each_turn():
    bot = _build_bot()
    applied = []
    bot._apply_advancement = lambda user_message: applied.append(user_message)

    history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]
    bot.replay(history)

    assert bot.flow_engine.added_turns == [("u1", "a1"), ("u2", "a2")]
    assert applied == ["u1", "u2"]


def test_replay_rejects_incomplete_history():
    bot = _build_bot()

    history = [{"role": "user", "content": "u1"}]

    try:
        bot.replay(history)
        assert False, "Expected replay to reject incomplete history"
    except ValueError as exc:
        assert "complete user/assistant turns" in str(exc)


def test_fallback_provider_runs_post_turn_hooks(monkeypatch):
    bot = _build_bot()
    bot._provider_name = "groq"
    bot._model_name = "primary-model"
    bot.provider = object()
    bot._router = type(
        "Router",
        (),
        {"provider": None, "provider_name": "groq", "model_name": "primary-model"},
    )()
    bot._apply_layer3_checks = lambda reply_text, user_message, provider_name=None: type(
        "GuardrailResult",
        (),
        {"content": reply_text},
    )()
    bot._apply_advancement = lambda user_message: setattr(
        bot.flow_engine, "flow_type", "consultative"
    )
    saved = []
    bot.save_session = lambda: saved.append(True)

    class _Analytics:
        def __init__(self):
            self.latency_calls = []

        def log_stage_latency(self, **kwargs):
            self.latency_calls.append(kwargs)

        def record_objection_classified(self, **kwargs):
            pass

    bot._analytics = _Analytics()

    class FallbackProvider:
        provider_name = "sambanova"

        def is_available(self):
            return True

        def get_model_name(self):
            return "fallback-model"

        def chat(self, *_args, **_kwargs):
            return LLMResponse(content="fallback reply", latency_ms=7.0)

    monkeypatch.setattr("core.chatbot.list_fallback_providers", lambda _name: ["sambanova"])
    monkeypatch.setattr("core.chatbot.create_provider", lambda _name: FallbackProvider())

    response = bot._try_fallback_providers([], "hello")

    assert response is not None
    assert response.content == "fallback reply"
    assert bot.provider_type == "sambanova"
    assert bot._provider_name == "sambanova"
    assert bot._model_name == "fallback-model"
    assert bot.flow_engine.added_turns == [("hello", "fallback reply")]
    assert bot.flow_engine.flow_type == "consultative"
    assert len(bot._turn_snapshots) == 1
    assert saved == [True]
    assert bot._analytics.latency_calls[0]["provider"] == "sambanova"


def test_save_session_uses_session_persistence_payload(monkeypatch):
    bot = _build_bot()
    bot.flow_engine.flow_type = "consultative"
    bot.flow_engine.current_stage = "pitch"
    bot.flow_engine.stage_turn_count = 3
    bot.flow_engine.initial_flow_type = "consultative"
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    bot._turn_snapshots = [{"flow_type": "consultative"}]
    captured = {}

    def _fake_save(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(SessionPersistence, "save", staticmethod(_fake_save))
    bot.save_session()

    assert captured == {
        "session_id": "session123",
        "product_type": "default",
        "provider_type": "probe",
        "flow_type": "consultative",
        "current_stage": "pitch",
        "stage_turn_count": 3,
        "conversation_history": [
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
        ],
        "initial_flow_type": "consultative",
        "turn_snapshots": [{"flow_type": "consultative"}],
    }


def test_session_persistence_round_trips_in_temp_directory(monkeypatch):
    temp_dir = Path.cwd() / ".tmp" / "session-persistence"
    temp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("core.session_persistence.SESSIONS_DIR", str(temp_dir))

    saved = SessionPersistence.save(
        session_id="persist123",
        product_type="default",
        provider_type="probe",
        flow_type="intent",
        current_stage="intent",
        stage_turn_count=0,
        conversation_history=[{"role": "user", "content": "hello"}],
        initial_flow_type="intent",
        turn_snapshots=[{"flow_type": "intent"}],
    )

    assert saved is True
    assert SessionPersistence.load("persist123") == {
        "session_id": "persist123",
        "product_type": "default",
        "provider_type": "probe",
        "flow_type": "intent",
        "current_stage": "intent",
        "stage_turn_count": 0,
        "conversation_history": [{"role": "user", "content": "hello"}],
        "initial_flow_type": "intent",
        "turn_snapshots": [{"flow_type": "intent"}],
    }


def test_prospect_session_persistence_saves_loads_and_deletes(monkeypatch):
    temp_dir = Path.cwd() / ".tmp" / "prospect-persistence"
    temp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("core.prospect_session_persistence.SESSIONS_DIR", str(temp_dir))

    state = {"difficulty": "medium", "history": ["hello"]}

    assert ProspectSessionPersistence.save("prospect123", state) is True
    assert ProspectSessionPersistence.load("prospect123") == state
    assert ProspectSessionPersistence.delete("prospect123") is True
    assert ProspectSessionPersistence.load("prospect123") is None
