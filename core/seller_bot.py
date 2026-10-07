"""Seller-mode bot: the script engine picks every line; this class keeps the call's history,
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
from .script_engine.seller import build_seller, selling_config
from .enums import Stage
from . import trainer, quiz

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

    def __init__(
        self,
        provider_type=None,
        model=None,
        product_type=None,
        session_id=None,
        record_session_start: bool = True,
    ):
        self._router = ProviderRouter(provider_type=provider_type, model=model)
        self.session_id = session_id
        cfg = selling_config()
        # only scripted products can be sold; anything else gets the default script
        self.product_type = product_type if product_type in cfg["products"] else cfg["default_product"]
        self.logger = logging.LoggerAdapter(
            _base_logger, {"session_id": session_id or "-"}
        )
        self.flow_engine = CallFlow()
        self.seller = build_seller(self._router, self.product_type)

        self._turn_snapshots = []

        if session_id and record_session_start:
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
        self.flow_engine.conversation_history.append({"role": "assistant", "content": greeting})
        self._log_turn_event(None, greeting)
        self.save_session()

    def _log_turn_event(self, user_message: str | None, bot_reply: str) -> None:

        if not self.session_id:
            return

        SessionAnalytics.record(
            session_id=self.session_id,
            event="conversation_turn",
            turn_index=self.flow_engine.user_turn_count,
            strategy=self.flow_engine.flow_type,
            current_stage=self.flow_engine.current_stage,
            user_message=user_message,
            assistant_message=bot_reply,
        )

    def script_opening(self) -> str:
        """First line of the call (also sets its stage)."""
        text, ui_stage = self.seller.opening()
        self._show_stage(ui_stage)
        return text

    def _show_stage(self, ui_stage: str) -> None:
        if self.flow_engine.current_stage != ui_stage:
            self.flow_engine.advance(target_stage=Stage(ui_stage))

    def chat(self, user_message: str) -> ChatResponse:
        """One turn: the seller picks the line, then the usual bookkeeping."""
        start = time.time()
        text, ui_stage = self.seller.reply(user_message)
        self._show_stage(ui_stage)
        return self._complete_successful_turn(
            user_message=user_message,
            bot_reply=text,
            latency_ms=(time.time() - start) * 1000,
            turn_state=self.seller.state,  # saved in the snapshot so a rewind restores the script
        )

    def _build_response(
        self, content: str, latency_ms: float | None, user_message: str
    ) -> ChatResponse:
        """Build the standard response payload returned to the UI."""
        return ChatResponse(
            content=content,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self.model_name,
            input_len=len(user_message),
            output_len=len(content),
        )

    def _replay_turn(
        self,
        user_message: str,
        bot_reply: str,
        turn_state: dict[str, Any] | None = None,
    ) -> None:
        """Rebuild one finished turn from its saved script state."""
        if turn_state is not None:
            self.seller.reset(ScriptState(**turn_state))
        self._show_stage(self.seller.ui_stage())
        self.flow_engine.add_turn(user_message, bot_reply)

    def _complete_successful_turn(
        self,
        user_message: str,
        bot_reply: str,
        latency_ms: float | None,
        turn_state=None,
    ) -> ChatResponse:
        """Record a finished turn: history, analytics, snapshot."""
        self.flow_engine.add_turn(user_message, bot_reply)
        self._log_turn_event(user_message, bot_reply)

        if self.session_id:
            PerformanceTracker.log_stage_latency(
                session_id=self.session_id,
                stage=self.flow_engine.current_stage,
                strategy=self.flow_engine.flow_type,
                latency_ms=latency_ms,
                provider=self.provider_name,
                model=self.model_name,
                user_message_length=len(user_message),
                bot_response_length=len(bot_reply),
            )

        self.save_session()
        self._save_turn_snapshot(turn_state=turn_state)

        return self._build_response(bot_reply, latency_ms, user_message)

    def generate_training(self, user_msg: str, bot_reply: str) -> dict[str, Any]:
        """Coach notes for the current exchange: the script step itself (no AI call)."""
        return self.seller.training()

    def answer_training_question(
        self, question: str, style: str = "tactical"
    ) -> dict[str, Any]:
        """Answer a trainee's question about the current conversation and sales techniques."""
        return trainer.answer_training_question(
            self._router, self.flow_engine, question, style
        )

    def run_quiz_stage_answer(self, answer: str) -> dict:
        """Check whether the user picked the right stage for the current moment."""
        return quiz.test_quiz_stage_answer(
            answer, self.flow_engine.current_stage, self.flow_engine.flow_type
        )

    def run_quiz_next_move(self, response: str) -> dict:
        """Score the user's suggested next move for the live conversation."""
        history = self.flow_engine.conversation_history
        last_user_msg = next(
            (m.get("content", "") for m in reversed(history) if m.get("role") == "user"),
            "",
        )
        return quiz.test_quiz_next_move(
            response, self._router, self.flow_engine.current_stage, self.flow_engine.flow_type, last_user_msg
        )

    def run_quiz_direction(self, explanation: str) -> dict:
        """Score the user's explanation of why the conversation should move next."""
        return quiz.test_quiz_direction(
            explanation, self._router, self.flow_engine.current_stage, self.flow_engine.flow_type
        )

    def _capture_turn_snapshot(self, turn_state=None) -> dict:
        """Capture current FSM state for snapshot-based rewinding."""
        if turn_state is None:
            turn_state = self.seller.state
        if turn_state is not None and not isinstance(turn_state, dict):
            turn_state = asdict(turn_state)
        snapshot = {
            "current_stage": self.flow_engine.current_stage,
            "stage_turn_count": self.flow_engine.stage_turn_count,
            "turn_state": turn_state,
        }
        return snapshot

    def _save_turn_snapshot(self, turn_state=None) -> None:
        """Save FSM snapshot after processing a turn (used for rewinding)."""
        self._turn_snapshots.append(self._capture_turn_snapshot(turn_state=turn_state))

    def rewind_to_turn(self, turn_index: int) -> bool:
        """Rewind to turn_index by loading FSM snapshot instead of replaying."""
        max_turns = len(self.flow_engine.conversation_history) // 2
        if turn_index < 0 or turn_index > max_turns:
            self.logger.warning(f"Invalid turn_index {turn_index}, max is {max_turns}")
            return False

        history_length = turn_index * 2
        if history_length > len(self.flow_engine.conversation_history):
            return False

        old_history = self.flow_engine.conversation_history[:history_length]
        self.flow_engine.conversation_history = old_history

        if turn_index == 0:
            self.flow_engine.reset_to_initial()
            self.seller.reset()
            self._turn_snapshots = []
            self.save_session()
            return True

        if turn_index <= len(self._turn_snapshots):
            snapshot = self._turn_snapshots[turn_index - 1]
            self.flow_engine.restore_state(snapshot)
            saved = snapshot.get("turn_state")
            self.seller.reset(ScriptState(**saved) if saved else None)
            self._turn_snapshots = self._turn_snapshots[:turn_index]
        else:
            self.logger.warning(f"Snapshot not available for turn {turn_index}, falling back to replay")
            self.flow_engine.reset_to_initial()
            self.seller.reset()
            saved_snapshots = list(self._turn_snapshots)
            self._turn_snapshots = []
            for idx, (user_msg_dict, bot_msg_dict) in enumerate(
                zip(old_history[::2], old_history[1::2]),
                start=1,
            ):
                user_msg = user_msg_dict.get("content", "")
                bot_msg = bot_msg_dict.get("content", "")
                snapshot = (
                    saved_snapshots[idx - 1]
                    if idx - 1 < len(saved_snapshots)
                    else None
                )
                turn_state = snapshot.get("turn_state") if snapshot else None
                self._replay_turn(user_msg, bot_msg, turn_state=turn_state)
                self._save_turn_snapshot(turn_state=turn_state)

        self.save_session()
        return True

    def edit_turn(self, message_index: int, new_text: str):
        """Rewind to the user message at message_index and replay it as new_text.

        Raises ValueError (message safe to show) for a bad index or a non-user
        message; returns None if the rewind fails, else the new ChatResponse.
        """
        history = self.flow_engine.conversation_history
        max_index = len(history) - 1
        if message_index < 0 or message_index > max_index:
            raise ValueError(f"Invalid index. Valid range: 0-{max_index}")
        if history[message_index].get("role") != "user":
            raise ValueError("Can only edit user messages")
        if not self.rewind_to_turn(message_index // 2):
            return None
        return self.chat(new_text)

    def save_session(self):
        """Emit a durable log snapshot of the current session state."""
        if not self.session_id:
            return
        fe = self.flow_engine
        snapshot = {
            "session_id": self.session_id,
            "product_type": self.product_type,
            "provider_type": self.provider_name,
            "current_stage": fe.current_stage,
            "stage_turn_count": fe.stage_turn_count,
            "turn_count": fe.user_turn_count,
            "message_count": len(fe.conversation_history),
        }
        self.logger.info("session_snapshot %s", json.dumps(snapshot, default=str))

    def record_session_end(self):
        """Record where this session actually got to, so finished sessions are counted."""
        if not self.session_id:
            return
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_end",
            final_stage=str(self.flow_engine.current_stage),
            strategy=str(self.flow_engine.flow_type),
            turn_count=self.flow_engine.user_turn_count,
            message_count=len(self.flow_engine.conversation_history),
        )
