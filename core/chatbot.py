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
from .objection import _get_objection_pathway_safe
from .constants import (
    RECENT_HISTORY_WINDOW,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
)
from .flow import SalesFlowEngine
from .services.analytics_recorder import AnalyticsRecorder
from .services.provider_router import ProviderRouter
from .providers import create_provider
from .providers import list_fallback_providers  # re-export for tests/patching
from .providers.base import ACCESS_DENIED, RATE_LIMIT, LLMResponse
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
        self.provider = self._router.provider
        self.provider_resolution = self._router.resolution
        self.session_id = session_id
        self.product_type = product_type
        self.provider_type = getattr(self.provider, "provider_name", provider_type)
        self.logger = logging.LoggerAdapter(
            _base_logger, {"session_id": session_id or "-"}
        )

        self._provider_name = self._router.provider_name
        self._model_name = self._router.model_name

        self._analytics = AnalyticsRecorder()

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

        self._ab_variant = assign_ab_variant(session_id) if session_id else None
        self._turn_snapshots = []

        if session_id and record_session_start:
            self._analytics.record_session_start(
                session_id=session_id,
                product_type=product_type or "unknown",
                initial_strategy=str(self.flow_engine.flow_type),
                ab_variant=self._ab_variant,
            )

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def _log_turn_event(self, user_message: str, bot_reply: str) -> None:

        if not self.session_id:
            return

        turn_count = getattr(
            self.flow_engine,
            "user_turn_count",
            sum(1 for m in getattr(self.flow_engine, "conversation_history", []) if m.get("role") == "user"),
        )

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

    def chat(self, user_message: str) -> ChatResponse:
        """Run one turn - returns reply content plus latency/provider metrics."""
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
                    self._analytics.record_stage_transition(
                        session_id=self.session_id,
                        from_stage=str(old_stage),
                        to_stage=str(self.flow_engine.current_stage),
                        strategy=str(self.flow_engine.flow_type),
                        user_turns_in_stage=self.flow_engine.stage_turn_count,
                    )

        objection_data = None
        if str(self.flow_engine.current_stage).lower() == "objection" and user_message:
            objection_data = _get_objection_pathway_safe(
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
            self._analytics.record_intent_classification(
                session_id=self.session_id,
                intent_level=turn_state.intent,
                user_turn_count=self.flow_engine.user_turn_count + 1,
            )

        request_start = time.time()
        try:
            llm_response = self.provider.chat(
                llm_messages,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=DEFAULT_MAX_TOKENS,
                stage=self.flow_engine.current_stage,
            )

            if llm_response.error or not llm_response.content:
                return self._handle_provider_error(
                    llm_response, llm_messages, user_message
                )

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
            provider=self._provider_name,
            model=self._model_name,
            input_len=len(user_message),
            output_len=len(content),
        )

    def _apply_layer3_checks(
        self,
        reply_text: str,
        user_message: str,
        provider_name: str | None = None,
    ) -> Layer3CheckResult:
        """Run LAYER 3 (Response Validation) checks on LLM output.

        Detects and blocks rule violations before sending response to user.
        Probe provider returns JSON payloads for tests and must remain unmodified.
        """
        active_provider = (provider_name or self._provider_name or "").lower()
        if active_provider == "probe":
            return Layer3CheckResult(content=reply_text)

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

    def _handle_provider_error(
        self, llm_response: LLMResponse, llm_messages: list, user_message: str
    ) -> ChatResponse:
        """Handle provider failures and try fallback routes when it makes sense."""
        if self._is_rate_limit(llm_response):
            self.logger.warning(
                f"rate limit on {self._provider_name}: {llm_response.error}"
            )
            retry = self._try_fallback_providers(llm_messages, user_message)
            if retry is not None:
                return retry
            return self._fallback(
                "Too much traffic right now - give it a second and try that again.",
                llm_response.latency_ms,
                user_message,
            )

        self.logger.warning(
            "provider error on %s: %s",
            self._provider_name,
            llm_response.error,
        )
        retry = self._try_fallback_providers(llm_messages, user_message)
        if retry is not None:
            return retry

        if self._is_network_access_denied(llm_response):
            self.logger.error(
                "network access denied for %s: %s",
                self._provider_name,
                llm_response.error,
            )
            return self._fallback(
                f"{self._provider_name.capitalize()} is rejecting this request (access denied). "
                "Check the API key, VPN/proxy, firewall, or provider-side security rules, then try again.",
                llm_response.latency_ms,
                user_message,
            )

        return self._fallback(
            "Can't reach the Bot right now - give it another go.",
            llm_response.latency_ms,
            user_message,
        )

    def _sync_provider_from_router(self, alt_provider, next_name: str) -> None:
        """Update all provider references after switching to a fallback provider."""
        self.provider = alt_provider
        self.provider_type = next_name
        self._provider_name = next_name
        self._model_name = alt_provider.get_model_name()
        if self._router is not None:
            self._router.provider = alt_provider
            self._router.provider_name = next_name
            self._router.model_name = self._model_name

    def _try_fallback_providers(
        self, llm_messages: list, user_message: str
    ) -> ChatResponse | None:
        """Try other configured providers until one returns a usable reply."""
        for next_name in list_fallback_providers(self._provider_name):
            try:
                alt = create_provider(next_name)
                if not alt.is_available():
                    continue
                resp = alt.chat(
                    llm_messages,
                    temperature=DEFAULT_TEMPERATURE,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    stage=self.flow_engine.current_stage,
                )
                if resp.error or not resp.content:
                    self.logger.warning(
                        "fallback provider %s unavailable: %s",
                        next_name,
                        resp.error or "empty response",
                    )
                    continue

                self._sync_provider_from_router(alt, next_name)
                self.logger.info(f"switched to {next_name} after error")
                return self._complete_successful_turn(
                    user_message=user_message,
                    bot_reply=resp.content,
                    latency_ms=resp.latency_ms,
                    advanced_this_turn=False,
                    turn_state=analyse_state(self.flow_engine.conversation_history, user_message),
                )
            except Exception as e:
                self.logger.error(f"fallback to {next_name} failed: {e}")
        return None

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
                self._analytics.record_strategy_switch(
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
            self._analytics.log_stage_latency(
                session_id=self.session_id,
                stage=self.flow_engine.current_stage,
                strategy=self.flow_engine.flow_type,
                latency_ms=latency_ms,
                provider=self._provider_name,
                model=self._model_name,
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
                objection_data = _get_objection_pathway_safe(
                    user_message, self.flow_engine.conversation_history
                )
            objection_type = (
                objection_data.get("type", "unknown")
                if isinstance(objection_data, dict)
                else "unknown"
            )
            self._analytics.record_objection_classified(
                session_id=self.session_id,
                objection_type=objection_type,
                strategy=str(self.flow_engine.flow_type),
                user_turn_count=self.flow_engine.user_turn_count,
            )

        return self._build_response(bot_reply, latency_ms, user_message)

    def generate_training(self, user_msg: str, bot_reply: str) -> dict[str, Any]:
        """Generate coaching notes for the current exchange via lightweight LLM call."""
        return trainer.generate_training(
            self.provider, self.flow_engine, user_msg, bot_reply
        )

    def answer_training_question(
        self, question: str, style: str = "tactical"
    ) -> dict[str, Any]:
        """Answer a trainee's question about the current conversation and sales techniques."""
        return trainer.answer_training_question(
            self.provider, self.flow_engine, question, style
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
            response, self.provider, self.flow_engine.current_stage, self.flow_engine.flow_type, last_user_msg
        )

    def run_quiz_direction(self, explanation: str) -> dict:
        """Score the user's explanation of why the conversation should move next."""
        return quiz.test_quiz_direction(
            explanation, self.provider, self.flow_engine.current_stage, self.flow_engine.flow_type
        )

    def _capture_turn_snapshot(self, turn_state=None) -> dict:
        """Capture current FSM state for snapshot-based rewinding."""
        return {
            "flow_type": self.flow_engine.flow_type,
            "current_stage": self.flow_engine.current_stage,
            "stage_turn_count": self.flow_engine.stage_turn_count,
            "initial_flow_type": self.flow_engine.initial_flow_type,
            "turn_state": asdict(turn_state) if turn_state is not None else None,
        }

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

    def rewind(self, steps: int):
        """Rewind back by `steps` turns from the current position."""
        current_turns = len(self.flow_engine.conversation_history) // 2
        return self.rewind_to_turn(max(0, current_turns - steps))

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
            self._turn_snapshots = []
            self.save_session()
            return True

        if turn_index <= len(self._turn_snapshots):
            snapshot = self._turn_snapshots[turn_index - 1]
            self.flow_engine.restore_state(snapshot)
            self._turn_snapshots = self._turn_snapshots[:turn_index]
        else:
            self.logger.warning(f"Snapshot not available for turn {turn_index}, falling back to replay")
            self.flow_engine.reset_to_initial()
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
        summary.update({"provider": self._provider_name, "model": self._model_name})
        return summary

    def save_session(self):
        """Emit a durable log snapshot of the current session state."""
        if not self.session_id:
            return
        try:
            self.logger.info(
                "session_snapshot %s",
                json.dumps(
                    {
                        "session_id": self.session_id,
                        "product_type": self.product_type,
                        "provider_type": self.provider_type,
                        "flow_type": self.flow_engine.flow_type,
                        "current_stage": self.flow_engine.current_stage,
                        "stage_turn_count": self.flow_engine.stage_turn_count,
                        "initial_flow_type": self.flow_engine.initial_flow_type,
                        "turn_count": getattr(
                            self.flow_engine,
                            "user_turn_count",
                            sum(1 for m in getattr(self.flow_engine, "conversation_history", []) if m.get("role") == "user"),
                        ),
                        "message_count": len(self.flow_engine.conversation_history),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
        except Exception as e:
            self.logger.exception(
                "Exception while logging session %s: %s", self.session_id, e
            )

    def record_session_end(self):
        """Record session completion for evaluation analytics."""
        if not self.session_id:
            return
        # Session events (start, stage transitions, strategy switches) are
        # recorded throughout the conversation lifecycle via SessionAnalytics.

    @staticmethod
    def load_session(session_id):
        """Disk recovery is disabled; in-memory sessions are the only live state."""

        logging.getLogger(__name__).debug("session_load_disabled session_id=%s", session_id)
        return None
