"""The buy-mode seller rewinds and replays a call from its turn snapshots."""
import logging
from typing import Any, cast

from core.flow import CallFlow
from core.script_engine.engine import ScriptState
from core.seller_bot import SellerBot


class _FakeSeller:
    def __init__(self):
        self.state = ScriptState(step="01")
        self.resets = []

    def reset(self, state=None):
        self.resets.append(state)
        self.state = state or ScriptState(step="01")


def _build_bot() -> Any:
    bot = cast(Any, SellerBot.__new__(SellerBot))
    bot.call = CallFlow()
    bot.seller = _FakeSeller()
    bot._turn_snapshots = []
    bot.session_id = "session123"
    bot.product_type = "high_ticket_sales_mentorship"
    bot._router = type("Router", (), {"provider": None, "provider_name": "probe", "model_name": "probe-model"})()
    bot.logger = logging.getLogger("test-seller")
    return bot


def _two_turns(bot):
    bot.call.conversation_history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]


def test_rewind_to_zero_turn_resets_state_and_clears_snapshots(monkeypatch):
    bot = _build_bot()
    _two_turns(bot)
    bot.call.advance("logical")
    bot._turn_snapshots = [{"current_stage": "logical"}]
    saved = []
    monkeypatch.setattr(bot, "log_snapshot", lambda: saved.append(True))

    assert bot.rewind_to_turn(0) is True
    assert bot.call.conversation_history == []
    assert bot.call.current_stage == "intent"
    assert bot.seller.resets == [None]
    assert bot._turn_snapshots == []
    assert saved == [True]


def test_rewind_to_turn_restores_stage_and_script_state(monkeypatch):
    bot = _build_bot()
    _two_turns(bot)
    bot._turn_snapshots = [
        {"current_stage": "logical", "stage_turn_count": 1, "turn_state": {"step": "02"}},
        {"current_stage": "pitch", "stage_turn_count": 2, "turn_state": {"step": "09"}},
    ]
    monkeypatch.setattr(bot, "log_snapshot", lambda: None)

    assert bot.rewind_to_turn(1) is True
    assert bot.call.conversation_history == [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    assert bot.call.current_stage == "logical"
    assert bot.seller.state == ScriptState(step="02")
    assert len(bot._turn_snapshots) == 1


def test_turn_snapshot_keeps_the_script_state():
    bot = _build_bot()
    bot.seller.state = ScriptState(step="03", last_point="the money")

    snap = bot._capture_turn_snapshot()
    assert snap["current_stage"] == "intent"
    assert snap["turn_state"]["step"] == "03"
    assert snap["turn_state"]["last_point"] == "the money"


def test_log_snapshot_logs_the_session_state(caplog):
    bot = _build_bot()
    bot.call.advance("pitch")
    caplog.set_level(logging.INFO)

    assert bot.log_snapshot() is None
    assert any(
        "session_snapshot" in record.message and "session123" in record.message
        for record in caplog.records
    )


def test_edit_turn_rejects_bad_index_and_assistant_message_without_rewinding():
    bot = _build_bot()
    bot.call.conversation_history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    bot.chat = lambda text: (_ for _ in ()).throw(AssertionError("must not replay"))

    for index, message in ((5, "Invalid index. Valid range: 0-1"), (1, "Can only edit user messages")):
        try:
            bot.edit_turn(index, "new")
        except ValueError as error:
            assert str(error) == message
        else:
            raise AssertionError("expected ValueError")
    assert len(bot.call.conversation_history) == 2


def test_edit_after_the_opening_greeting_keeps_the_greeting_and_earlier_turns(monkeypatch):
    """A buy session opens with the seller's greeting, so the learner's turns sit at odd indexes."""
    bot = _build_bot()
    bot.call.conversation_history = [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
    ]
    bot._turn_snapshots = [
        {"current_stage": "logical", "stage_turn_count": 1, "turn_state": {"step": "02"}},
        {"current_stage": "pitch", "stage_turn_count": 2, "turn_state": {"step": "09"}},
    ]
    monkeypatch.setattr(bot, "log_snapshot", lambda: None)
    replayed = []
    bot.chat = lambda text: replayed.append((text, list(bot.call.conversation_history))) or "reply"

    assert bot.edit_turn(3, "u2 again") == "reply"

    text, history_before_replay = replayed[0]
    assert text == "u2 again"
    assert history_before_replay == [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    assert bot.seller.state == ScriptState(step="02")


def test_editing_the_first_turn_keeps_the_opening_greeting(monkeypatch):
    bot = _build_bot()
    bot.call.conversation_history = [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    bot._turn_snapshots = [{"current_stage": "logical", "stage_turn_count": 1, "turn_state": {"step": "02"}}]
    monkeypatch.setattr(bot, "log_snapshot", lambda: None)
    replayed = []
    bot.chat = lambda text: replayed.append(list(bot.call.conversation_history)) or "reply"

    bot.edit_turn(1, "u1 again")

    assert replayed == [[{"role": "assistant", "content": "hello"}]]
    assert bot._turn_snapshots == []
