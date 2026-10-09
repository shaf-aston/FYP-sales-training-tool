"""Buy mode's AI seller: the script engine picks every line; this class keeps the call's history,
rewind snapshots and analytics."""

import json
import logging
import time
from dataclasses import asdict, dataclass

from typing import Any, Optional

from .flow import CallFlow
from .analytics.performance import PerformanceTracker
from .analytics.session_analytics import SessionAnalytics
from .services.provider_router import ProviderRouter
from .script_engine.engine import ScriptState
from .script_engine.seller import build_seller, resolve_product
from .enums import Stage
from . import coach, quiz

_base_logger = logging.getLogger(__name__)


@dataclass
class ChatResponse:
    content: str
    latency_ms: Optional[float] = None  # ms; None if provider didn't report
    provider: Optional[str] = None
    model: Optional[str] = None
    input_len: int = 0
    output_len: int = 0


class SellerBot:
    """Runs one scripted sales call and logs each turn."""

    def __init__(self, provider_type=None, product_type=None, session_id=None):
        self._router = ProviderRouter(provider_type=provider_type)
        self.session_id = session_id
        self.product_type = resolve_product(product_type)  # only scripted products can be sold
        self.logger = logging.LoggerAdapter(_base_logger, {"session_id": session_id or "-"})
        self.call = CallFlow()
        self.seller = build_seller(self._router, self.product_type)
        # One per learner turn: the stage and script state right after it, for rewinding.
        self._turn_snapshots = []

        if session_id:
            SessionAnalytics.record(
                event="session_start",
                session_id=session_id,
                product_type=self.product_type,
            )

    @property
    def provider_name(self) -> str:
        return self._router.provider_name

    @property
    def model_name(self) -> str:
        return self._router.model_name

    def open_with(self, greeting: str) -> None:
        """Put the opening line in the history (so the AI never re-greets) and record it as turn 0."""
        self.call.conversation_history.append({"role": "assistant", "content": greeting})
        self._log_turn_event(None, greeting)
        self.log_snapshot()

    def _log_turn_event(self, user_message: str | None, seller_reply: str) -> None:
        if not self.session_id:
            return
        SessionAnalytics.record(
            session_id=self.session_id,
            event="conversation_turn",
            turn_index=self.call.user_turn_count,
            strategy=self.call.strategy,
            current_stage=self.call.current_stage,
            user_message=user_message,
            assistant_message=seller_reply,
        )

    def script_opening(self) -> str:
        """First line of the call (also sets its stage)."""
        text, ui_stage = self.seller.opening()
        self._show_stage(ui_stage)
        return text

    def _show_stage(self, ui_stage: str) -> None:
        if self.call.current_stage != ui_stage:
            self.call.advance(target_stage=Stage(ui_stage))

    def chat(self, user_message: str) -> ChatResponse:
        """One turn: the seller picks the line, then history, analytics and the rewind snapshot."""
        start = time.time()
        text, ui_stage = self.seller.reply(user_message)
        self._show_stage(ui_stage)
        latency_ms = (time.time() - start) * 1000

        self.call.add_turn(user_message, text)
        self._log_turn_event(user_message, text)
        if self.session_id:
            PerformanceTracker.log_latency(self.provider_name, self.model_name, latency_ms)
        self.log_snapshot()
        self._turn_snapshots.append(self._capture_turn_snapshot())

        return ChatResponse(
            content=text,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self.model_name,
            input_len=len(user_message),
            output_len=len(text),
        )

    def coach_notes(self) -> dict[str, Any]:
        """Coach notes for the current point of the call: the script step itself (no AI call)."""
        return self.seller.coach_notes()

    def answer_coach_question(self, question: str, style: str = coach.DEFAULT_STYLE) -> dict[str, Any]:
        return coach.answer_question(self._router, self.call, question, style)

    def score_stage_answer(self, answer: str) -> dict:
        return quiz.score_stage_answer(answer, self.call.current_stage, self.call.strategy)

    def score_next_move(self, response: str) -> dict:
        history = self.call.conversation_history
        last_user_msg = next(
            (m.get("content", "") for m in reversed(history) if m.get("role") == "user"),
            "",
        )
        return quiz.score_next_move(
            response, self._router, self.call.current_stage, self.call.strategy, last_user_msg
        )

    def score_direction(self, explanation: str) -> dict:
        return quiz.score_direction(explanation, self._router, self.call.current_stage, self.call.strategy)

    def _capture_turn_snapshot(self) -> dict:
        turn_state = self.seller.state
        if turn_state is not None and not isinstance(turn_state, dict):
            turn_state = asdict(turn_state)
        return {
            "current_stage": self.call.current_stage,
            "stage_turn_count": self.call.stage_turn_count,
            "turn_state": turn_state,
        }

    def rewind_to_turn(self, turn_index: int) -> bool:
        """Put the call back to just after the learner's `turn_index`-th turn (0 = only the greeting)."""
        history = self.call.conversation_history
        user_positions = [i for i, m in enumerate(history) if m.get("role") == "user"]
        if not 0 <= turn_index <= min(len(user_positions), len(self._turn_snapshots)):
            self.logger.warning(f"Invalid turn_index {turn_index}, max is {len(user_positions)}")
            return False

        kept = history[:user_positions[turn_index]] if turn_index < len(user_positions) else history
        if turn_index == 0:
            self.call.reset_to_initial()
            self.seller.reset()
        else:
            snapshot = self._turn_snapshots[turn_index - 1]
            self.call.restore_state(snapshot)
            saved = snapshot.get("turn_state")
            self.seller.reset(ScriptState(**saved) if saved else None)
        self.call.conversation_history = kept
        self._turn_snapshots = self._turn_snapshots[:turn_index]
        self.log_snapshot()
        return True

    def edit_turn(self, message_index: int, new_text: str):
        """Rewind to the user message at message_index and replay it as new_text.

        Raises ValueError (message safe to show) for a bad index or a non-user
        message; returns None if the rewind fails, else the new ChatResponse.
        """
        history = self.call.conversation_history
        max_index = len(history) - 1
        if message_index < 0 or message_index > max_index:
            raise ValueError(f"Invalid index. Valid range: 0-{max_index}")
        if history[message_index].get("role") != "user":
            raise ValueError("Can only edit user messages")
        # The opening greeting comes first, so the turn is counted, not derived from the index.
        earlier_turns = sum(1 for m in history[:message_index] if m.get("role") == "user")
        if not self.rewind_to_turn(earlier_turns):
            return None
        return self.chat(new_text)

    def log_snapshot(self):
        """Write the session's current state to the log for monitoring (nothing is stored)."""
        if not self.session_id:
            return
        call = self.call
        snapshot = {
            "session_id": self.session_id,
            "product_type": self.product_type,
            "provider_type": self.provider_name,
            "current_stage": call.current_stage,
            "stage_turn_count": call.stage_turn_count,
            "turn_count": call.user_turn_count,
            "message_count": len(call.conversation_history),
        }
        self.logger.info("session_snapshot %s", json.dumps(snapshot, default=str))

    def record_session_end(self):
        """Record where this session actually got to, so finished sessions are counted."""
        if not self.session_id:
            return
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_end",
            final_stage=str(self.call.current_stage),
            strategy=str(self.call.strategy),
            turn_count=self.call.user_turn_count,
            message_count=len(self.call.conversation_history),
        )
