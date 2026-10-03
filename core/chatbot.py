"""Main chatbot class. Wires the provider, FSM engine and analytics together."""

import json
import logging
import time
from dataclasses import asdict, dataclass

from typing import Any, Optional

from .loader import (
    get_product_settings,
    assign_ab_variant,
)
from .analysis import (
    ConversationState,
    analyse_state,
)
from .objection import get_objection_pathway
from .constants import RECENT_HISTORY_WINDOW
from .flow import SalesFlowEngine
from .analytics.performance import PerformanceTracker
from .analytics.session_analytics import SessionAnalytics
from .services.provider_router import ProviderRouter
from .providers.base import ACCESS_DENIED, RATE_LIMIT, LLMResponse
from .script_engine.engine import ScriptState
from .script_engine.seller import build_seller, selling_config
from .response_guardrails import Layer3CheckResult, apply_layer3_output_checks
from .utils import Strategy, Stage
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


class SalesChatbot:
    """Ties the LLM provider to the FSM flow engine and logs each turn."""

    seller = None  # set in __init__ for scripted consultative calls

    def __init__(
        self,
        provider_type=None,
        model=None,
        product_type=None,
        session_id=None,
        record_session_start: bool = True,
    ):
        """Set up the provider, product context, flow engine, and analytics hooks."""
        self._router = ProviderRouter(provider_type=provider_type, model=model)
        self.session_id = session_id
        self.product_type = product_type
        self.logger = logging.LoggerAdapter(
            _base_logger, {"session_id": session_id or "-"}
        )


        config = get_product_settings(product_type or "")

        product_context = config["context"]
        if "knowledge" in config:
            product_context = (
                f"{config['context']}\n\nPRODUCT KNOWLEDGE:\n{config['knowledge']}"
            )

        try:
            from .knowledge import get_custom_knowledge_text

            custom_knowledge = get_custom_knowledge_text()
            if custom_knowledge:
                product_context += (
                    "\n\n--- BEGIN CUSTOM PRODUCT DATA ---\n"
                    f"{custom_knowledge}\n"
                    "--- END CUSTOM PRODUCT DATA ---"
                )
        except (ImportError, OSError, ValueError) as e:
            _base_logger.debug(f"Custom knowledge not loaded: {e}")

        self.flow_engine = SalesFlowEngine(
            flow_type=config["strategy"],
            product_context=product_context,
        )

        self.seller = None
        self._sync_seller()

        self._ab_variant = assign_ab_variant(session_id) if session_id else None
        self._turn_snapshots = []

        if session_id and record_session_start:
            SessionAnalytics.record(
                event="session_start",
                session_id=session_id,
                product_type=product_type or "unknown",
                initial_strategy=str(self.flow_engine.flow_type),
                ab_variant=self._ab_variant,
            )

    @property
    def provider_name(self) -> str:
        return self._router.provider_name

    @property
    def model_name(self) -> str:
        return self._router.model_name

    def _log_turn_event(self, user_message: str, bot_reply: str) -> None:

        if not self.session_id:
            return

        turn_count = self.flow_engine.user_turn_count

        payload = {
            "session_id": self.session_id,
            "turn_index": turn_count,
            "flow_type": self.flow_engine.flow_type,
            "current_stage": self.flow_engine.current_stage,
            "strategy": self.flow_engine.flow_type,
            "user_message": user_message,
            "assistant_message": bot_reply,
        }
        self.logger.info("conversation_turn %s", json.dumps(payload, ensure_ascii=False))

    def _sync_seller(self) -> bool:
        """Scripted selling runs only while the flow is consultative; True when it just switched on."""
        scripted = selling_config()["enabled"] and self.flow_engine.flow_type == Strategy.CONSULTATIVE
        if not scripted:
            self.seller = None
            return False
        if self.seller:
            return False
        self.seller = build_seller(self._router)
        return True

    def script_opening(self) -> str | None:
        """First line of a scripted call (also sets its stage), or None when not scripted."""
        if not self.seller:
            return None
        text, ui_stage = self.seller.opening()
        self._show_stage(ui_stage)
        return text

    def _show_stage(self, ui_stage: str) -> None:
        if self.flow_engine.current_stage != ui_stage:
            self.flow_engine.advance(target_stage=Stage(ui_stage))

    def _scripted_chat(self, user_message: str) -> ChatResponse:
        """One scripted turn: the seller picks the line, the usual turn bookkeeping follows."""
        start = time.time()
        text, ui_stage = self.seller.reply(user_message)
        self._show_stage(ui_stage)
        return self._complete_successful_turn(
            user_message=user_message,
            bot_reply=text,
            latency_ms=(time.time() - start) * 1000,
            advanced_this_turn=True,  # the script, not the FSM, moves the stage
            turn_state=self.seller.state,  # saved in the snapshot so a rewind restores the script
        )

    def chat(self, user_message: str) -> ChatResponse:
        """Run one turn - returns reply content plus latency/provider metrics."""
        if self._sync_seller():
            # the flow turned consultative mid-call (intent detection or a strategy switch): open the script
            start = time.time()
            return self._complete_successful_turn(
                user_message=user_message,
                bot_reply=self.script_opening(),
                latency_ms=(time.time() - start) * 1000,
                advanced_this_turn=True,
                turn_state=self.seller.state,
            )
        if self.seller:
            return self._scripted_chat(user_message)
        recent_history = self.flow_engine.conversation_history[-RECENT_HISTORY_WINDOW:]

        # Signal Detection (prerequisite): Analyze user state for all downstream layers.
        turn_state = analyse_state(self.flow_engine.conversation_history, user_message)

        # LAYER 1 (Stage-Gating): Check advancement conditions via FSM.
        # Prevents skipping stages and enforces conversation pacing.
        advanced_this_turn = False
        if self.flow_engine.flow_type != Strategy.INTENT:
            old_stage = self.flow_engine.current_stage
            target = self.flow_engine.should_advance(user_message, turn_state=turn_state)
            if target and target != old_stage:
                self.flow_engine.advance(target_stage=target)
                advanced_this_turn = True
                if self.session_id:
                    SessionAnalytics.record(
                        event="stage_transition",
                        session_id=self.session_id,
                        from_stage=str(old_stage),
                        to_stage=str(self.flow_engine.current_stage),
                        strategy=str(self.flow_engine.flow_type),
                        user_turns_in_stage=self.flow_engine.stage_turn_count,
                    )

        objection_data = None
        if str(self.flow_engine.current_stage).lower() == "objection" and user_message:
            objection_data = get_objection_pathway(
                user_message, self.flow_engine.conversation_history
            )

        # LAYER 2 (Prompt Rules): Assemble system prompt with stage-specific rules.
        # Rules guide LLM to self-constrain during generation.
        system_prompt = self.flow_engine.get_current_prompt(
            user_message,
            objection_data=objection_data,
            turn_state=turn_state,
            include_history=False,
        )
        llm_messages = (
            [{"role": "system", "content": system_prompt}]
            + recent_history
            + [{"role": "user", "content": user_message}]
        )

        if self.session_id:
            # history doesn't include this turn yet; count the message we're about to add
            SessionAnalytics.record(
                event="intent_classification",
                session_id=self.session_id,
                intent_level=turn_state.intent,
                user_turn_count=self.flow_engine.user_turn_count + 1,
            )

        request_start = time.time()
        try:
            result = self._router.chat_with_fallback(
                llm_messages, stage=self.flow_engine.current_stage
            )
            llm_response = result.response
            if not result.ok:
                return self._provider_failure_reply(llm_response, user_message)

            return self._complete_successful_turn(
                user_message=user_message,
                bot_reply=llm_response.content,
                latency_ms=llm_response.latency_ms,
                advanced_this_turn=advanced_this_turn,
                objection_data=objection_data,
                turn_state=turn_state,
            )

        except Exception:
            self.logger.exception("Unexpected error")
            return self._fallback(
                "Something went wrong. Can you try again?",
                (time.time() - request_start) * 1000,
                user_message,
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

    def _apply_layer3_checks(
        self,
        reply_text: str,
        user_message: str,
    ) -> Layer3CheckResult:
        """Run LAYER 3 (Response Validation) checks on LLM output.

        Detects and blocks rule violations before sending response to user.
        """
        result = apply_layer3_output_checks(
            reply_text=reply_text,
            stage=self.flow_engine.current_stage,
            user_message=user_message,
            flow_type=self.flow_engine.flow_type,
            history=self.flow_engine.conversation_history,
        )

        if result.was_blocked or result.was_corrected:
            self.logger.info(
                "layer3_output_checks applied: %s",
                ", ".join(result.applied_rules),
            )

        return result

    @staticmethod
    def _is_rate_limit(llm_response: LLMResponse) -> bool:
        """Return True when the provider error looks like rate limiting."""
        if getattr(llm_response, "error_code", None) == RATE_LIMIT:
            return True
        detail = str(llm_response.error or "").lower()
        return "rate_limit_exceeded" in detail or "429" in detail

    @staticmethod
    def _is_network_access_denied(llm_response: LLMResponse) -> bool:
        """Return True when the provider or network is rejecting the request."""
        if getattr(llm_response, "error_code", None) == ACCESS_DENIED:
            return True
        detail = str(llm_response.error or "").lower()
        return any(
            marker in detail
            for marker in (
                "winerror 10013",
                "forbidden by its access permissions",
                "socket in a way forbidden",
                "error code: 1010",
                "access denied",
            )
        )

    def _provider_failure_reply(
        self, llm_response: LLMResponse, user_message: str
    ) -> ChatResponse:
        """Explain an outage after every provider (primary and fallbacks) failed."""
        if self._is_rate_limit(llm_response):
            message = "Too much traffic right now - give it a second and try that again."
        elif self._is_network_access_denied(llm_response):
            self.logger.error(
                "network access denied for %s: %s", self.provider_name, llm_response.error
            )
            message = (
                f"{self.provider_name.capitalize()} is rejecting this request (access denied). "
                "Check the API key, VPN/proxy, firewall, or provider-side security rules, then try again."
            )
        else:
            message = "Can't reach the Bot right now - give it another go."
        return self._fallback(message, llm_response.latency_ms, user_message)

    def _fallback(
        self, message: str, latency_ms: float, user_message: str
    ) -> ChatResponse:
        """Return a UI-safe fallback reply without mutating conversation history."""
        # Don't append fallback messages to conversation_history to avoid corrupting
        # FSM context. The error message is returned in ChatResponse for UI display,
        # but must not be processed by the LLM on the next turn.
        return self._build_response(message, latency_ms, user_message)

    def _apply_advancement(self, user_message: str) -> None:
        """Handle INTENT strategy switch after the LLM responds."""
        if self.flow_engine.flow_type != Strategy.INTENT:
            return
        old_strategy = self.flow_engine.flow_type
        if self.flow_engine.evaluate_strategy_switch(user_message):
            if self.session_id and old_strategy != self.flow_engine.flow_type:
                SessionAnalytics.record(
                    event="strategy_switch",
                    session_id=self.session_id,
                    from_strategy=str(old_strategy),
                    to_strategy=str(self.flow_engine.flow_type),
                    reason="signal_detection",
                    user_turn_count=self.flow_engine.user_turn_count,
                )

    def _replay_turn(
        self,
        user_message: str,
        bot_reply: str,
        turn_state: dict[str, Any] | None = None,
    ) -> None:
        """Reconstruct one completed turn using the same advancement order as live chat."""
        if self.seller:
            if turn_state is not None:
                self.seller.reset(ScriptState(**turn_state))
            self._show_stage(self.method_stage())
            self.flow_engine.add_turn(user_message, bot_reply)
            return
        if turn_state is None:
            state = analyse_state(self.flow_engine.conversation_history, user_message)
        else:
            state = ConversationState(**turn_state)

        advanced_this_turn = False
        if self.flow_engine.flow_type != Strategy.INTENT:
            old_stage = self.flow_engine.current_stage
            target = self.flow_engine.should_advance(user_message, turn_state=state)
            if target and target != old_stage:
                self.flow_engine.advance(target_stage=target)
                advanced_this_turn = True

        self.flow_engine.add_turn(user_message, bot_reply)

        if not advanced_this_turn:
            self._apply_advancement(user_message)

    def _complete_successful_turn(
        self,
        user_message: str,
        bot_reply: str,
        latency_ms: float | None,
        advanced_this_turn: bool,
        objection_data: dict[str, Any] | None = None,
        turn_state=None,
    ) -> ChatResponse:
        """Finalize a successful reply so normal and fallback paths stay consistent."""
        # LAYER 3 (Response Validation): Final guardrail check before sending to user.
        guardrail_result = self._apply_layer3_checks(bot_reply, user_message)
        bot_reply = guardrail_result.content

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

        if not advanced_this_turn:
            self._apply_advancement(user_message)

        # Persist post-advancement state so stage/strategy changes are durable.
        self.save_session()
        self._save_turn_snapshot(turn_state=turn_state)

        if self.session_id and self.flow_engine.current_stage == Stage.OBJECTION:
            if objection_data is None:
                objection_data = get_objection_pathway(
                    user_message, self.flow_engine.conversation_history
                )
            objection_type = (
                objection_data.get("type", "unknown")
                if isinstance(objection_data, dict)
                else "unknown"
            )
            SessionAnalytics.record(
                event="objection_classified",
                session_id=self.session_id,
                objection_type=objection_type,
                strategy=str(self.flow_engine.flow_type),
                user_turn_count=self.flow_engine.user_turn_count,
            )

        return self._build_response(bot_reply, latency_ms, user_message)

    def generate_training(self, user_msg: str, bot_reply: str) -> dict[str, Any]:
        """Generate coaching notes for the current exchange via lightweight LLM call."""
        if self.seller:
            return self.seller.training()  # scripted call: the step itself is the coaching note
        return trainer.generate_training(
            self._router, self.flow_engine, user_msg, bot_reply
        )

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

    def method_stage(self) -> str:
        """The UI stage of the script step the call is on."""
        return self.seller.method.steps[self.seller.state.step].ui_stage

    def _capture_turn_snapshot(self, turn_state=None) -> dict:
        """Capture current FSM state for snapshot-based rewinding."""
        if turn_state is None and self.seller:
            turn_state = self.seller.state
        if turn_state is not None and not isinstance(turn_state, dict):
            turn_state = asdict(turn_state)
        snapshot = {
            "flow_type": self.flow_engine.flow_type,
            "current_stage": self.flow_engine.current_stage,
            "stage_turn_count": self.flow_engine.stage_turn_count,
            "initial_flow_type": self.flow_engine.initial_flow_type,
            "turn_state": turn_state,
        }
        return snapshot

    def _save_turn_snapshot(self, turn_state=None) -> None:
        """Save FSM snapshot after processing a turn (used for rewinding)."""
        self._turn_snapshots.append(self._capture_turn_snapshot(turn_state=turn_state))

    def refresh_current_turn_snapshot(self) -> None:
        """Refresh the snapshot for the current turn after an out-of-band FSM mutation."""
        current_turns = len(self.flow_engine.conversation_history) // 2
        if current_turns <= 0:
            return
        snapshot = self._capture_turn_snapshot()
        if len(self._turn_snapshots) >= current_turns:
            self._turn_snapshots[current_turns - 1] = snapshot
        else:
            self._turn_snapshots.append(snapshot)

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
            if self.seller:
                self.seller.reset()
            self._turn_snapshots = []
            self.save_session()
            return True

        if turn_index <= len(self._turn_snapshots):
            snapshot = self._turn_snapshots[turn_index - 1]
            self.flow_engine.restore_state(snapshot)
            if self.seller:
                saved = snapshot.get("turn_state")
                self.seller.reset(ScriptState(**saved) if saved else None)
            self._turn_snapshots = self._turn_snapshots[:turn_index]
        else:
            self.logger.warning(f"Snapshot not available for turn {turn_index}, falling back to replay")
            self.flow_engine.reset_to_initial()
            if self.seller:
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
                turn_state = None
                if snapshot:
                    # fall back to old key for snapshots persisted before the rename
                    turn_state = snapshot.get("turn_state", snapshot.get("pre_state"))
                self._replay_turn(user_msg, bot_msg, turn_state=turn_state)
                self._save_turn_snapshot(turn_state=turn_state)

        self.save_session()
        return True

    def replay(self, history: list[dict[str, str]]) -> None:
        """Replay a history list into a fresh bot, including strategy-switch detection.

        Use this instead of flow_engine.replay_history() - it applies _apply_advancement
        so intent → consultative/transactional switches are correctly reconstructed.
        """
        if len(history) % 2 != 0:
            raise ValueError("History must contain complete user/assistant turns")

        for idx in range(0, len(history), 2):
            user_msg_dict = history[idx]
            bot_msg_dict = history[idx + 1]
            if user_msg_dict.get("role") != "user" or bot_msg_dict.get("role") != "assistant":
                raise ValueError("History must alternate user and assistant turns")
            user_msg = user_msg_dict.get("content", "")
            bot_msg = bot_msg_dict.get("content", "")
            self._replay_turn(user_msg, bot_msg)

    def get_conversation_summary(self):
        """Return FSM state summary with provider info."""
        summary = self.flow_engine.get_summary()
        summary.update({"provider": self.provider_name, "model": self.model_name})
        return summary

    def save_session(self):
        """Emit a durable log snapshot of the current session state."""
        if not self.session_id:
            return
        fe = self.flow_engine
        snapshot = {
            "session_id": self.session_id,
            "product_type": self.product_type,
            "provider_type": self.provider_name,
            "flow_type": fe.flow_type,
            "current_stage": fe.current_stage,
            "stage_turn_count": fe.stage_turn_count,
            "initial_flow_type": fe.initial_flow_type,
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
