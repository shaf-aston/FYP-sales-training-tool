"""Tests for chatbot state persistence and recovery."""
import logging
import shutil
from pathlib import Path
from typing import Any, cast

from core.analysis import ConversationState
from core.chatbot import SalesChatbot


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
        self.user_turn_count = 0

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
    bot._router = type("Router", (), {"provider": None, "provider_name": "probe", "model_name": "probe-model"})()
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


def test_save_turn_snapshot_includes_pre_state():
    bot = _build_bot()
    pre_state = ConversationState(
        intent="high",
        guarded=False,
        question_fatigue=False,
        decisive=True,
        doubt=True,
        stakes=False,
    )

    bot._save_turn_snapshot(turn_state=pre_state)

    assert bot._turn_snapshots == [
        {
            "flow_type": "intent",
            "current_stage": "intent",
            "stage_turn_count": 0,
            "initial_flow_type": "intent",
            "turn_state": {
                "intent": "high",
                "guarded": False,
                "question_fatigue": False,
                "decisive": True,
                "terms": False,
                "doubt": True,
                "stakes": False,
            },
        }
    ]


def test_refresh_current_turn_snapshot_updates_latest_state():
    bot = _build_bot()
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]
    bot._turn_snapshots = [
        {
            "flow_type": "intent",
            "current_stage": "intent",
            "stage_turn_count": 1,
            "initial_flow_type": "intent",
            "turn_state": None,
        },
        {
            "flow_type": "intent",
            "current_stage": "intent",
            "stage_turn_count": 2,
            "initial_flow_type": "intent",
            "turn_state": None,
        },
    ]
    bot.flow_engine.flow_type = "consultative"
    bot.flow_engine.current_stage = "logical"
    bot.flow_engine.stage_turn_count = 0

    bot.refresh_current_turn_snapshot()

    assert bot._turn_snapshots[1]["flow_type"] == "consultative"
    assert bot._turn_snapshots[1]["current_stage"] == "logical"
    assert bot._turn_snapshots[1]["initial_flow_type"] == "intent"


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


def test_save_session_logs_state_snapshot(caplog):
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
    caplog.set_level(logging.INFO)

    assert bot.save_session() is None
    assert any(
        "session_snapshot" in record.message and "session123" in record.message
        for record in caplog.records
    )
