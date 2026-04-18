"""Main chatbot class. Wires the provider, FSM engine, and analytics together."""

import json
import logging
import os
import time
from dataclasses import dataclass

from typing import Any, Optional

from .loader import (
    get_product_settings,
    load_signals,
    assign_ab_variant,
    load_web_search_config,
)
from .analysis import (
    analyse_state,
    build_search_query,
    should_trigger_web_search,
)
from .objection import _get_objection_pathway_safe
from .constants import (
    MAX_SEARCH_RESULTS,
    MIN_SECONDS_BETWEEN_SEARCHES,
    SEARCH_CACHE_TTL_SECONDS,
    RECENT_HISTORY_WINDOW,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
    MIN_TURNS_BEFORE_ADVANCE,
)
from .flow import SalesFlowEngine
from .analytics.performance import PerformanceTracker
from .analytics.session_analytics import SessionAnalytics
from .providers import create_provider
from .providers.base import RATE_LIMIT, LLMResponse
from .utils import Strategy, Stage, contains_nonnegated_keyword
from .web_search import WebSearchService
from . import trainer
from .session_persistence import SessionPersistence

_base_logger = logging.getLogger(__name__)

_SIGNALS = load_signals()
_TRANSACTIONAL_INDICATORS = _SIGNALS.get("transactional_bot_indicators", [])
_CONSULTATIVE_INDICATORS = _SIGNALS.get("consultative_bot_indicators", [])
_USER_CONSULTATIVE_SIGNALS = _SIGNALS.get("user_consultativeSIGNALS", [])
_USER_TRANSACTIONAL_SIGNALS = _SIGNALS.get("user_transactionalSIGNALS", [])


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
        self, provider_type=None, model=None, product_type=None, session_id=None
    ):
        self.provider = create_provider(provider_type, model=model)
        self.session_id = session_id
        self.product_type = product_type
        self.provider_type = provider_type
        self.logger = logging.LoggerAdapter(
            _base_logger, {"session_id": session_id or "-"}
        )

        self._provider_name = (
            type(self.provider).__name__.replace("Provider", "").lower()
        )
        self._model_name = self.provider.get_model_name()

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

        self.ws_config = load_web_search_config()
        self.web_search = WebSearchService(
            cache_ttl=self.ws_config.get("cache_ttl_seconds", SEARCH_CACHE_TTL_SECONDS)
        )
        self.last_search_time: float = 0.0

        self._ab_variant = assign_ab_variant(session_id) if session_id else None

        if session_id:
            SessionAnalytics.record_session_start(
                session_id=session_id,
                product_type=product_type or "unknown",
                initial_strategy=str(self.flow_engine.flow_type),
                ab_variant=self._ab_variant,
            )

    def chat(self, user_message: str) -> ChatResponse:
        """Run one turn — returns reply content plus latency/provider metrics."""
        recent_history = self.flow_engine.conversation_history[-RECENT_HISTORY_WINDOW:]

        objection_data = None
        if str(self.flow_engine.current_stage).lower() == "objection" and user_message:
            objection_data = _get_objection_pathway_safe(
                user_message, self.flow_engine.conversation_history
            )

        system_prompt = self.flow_engine.get_current_prompt(
            user_message, objection_data=objection_data
        )
        search_context = self._maybe_enrich_with_search(
            user_message, objection_data=objection_data
        )
        if search_context:
            system_prompt += search_context

        llm_messages = (
            [{"role": "system", "content": system_prompt}]
            + recent_history
            + [{"role": "user", "content": user_message}]
        )

        if self.session_id:
            state = analyse_state(self.flow_engine.conversation_history, user_message)
            # history doesn't include this turn yet; count the message we're about to add
            SessionAnalytics.record_intent_classification(
                session_id=self.session_id,
                intent_level=state.intent,
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

            bot_reply = llm_response.content
            self.flow_engine.add_turn(user_message, bot_reply)
            self.save_session()

            if self.session_id:
                PerformanceTracker.log_stage_latency(
                    session_id=self.session_id,
                    stage=self.flow_engine.current_stage,
                    strategy=self.flow_engine.flow_type,
                    latency_ms=llm_response.latency_ms,
                    provider=self._provider_name,
                    model=self._model_name,
                    user_message_length=len(user_message),
                    bot_response_length=len(bot_reply),
                )

            self._apply_advancement(user_message)

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
                SessionAnalytics.record_objection_classified(
                    session_id=self.session_id,
                    objection_type=objection_type,
                    strategy=str(self.flow_engine.flow_type),
                    user_turn_count=self.flow_engine.user_turn_count,
                )

            return self._build_response(
                bot_reply, llm_response.latency_ms, user_message
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
        return ChatResponse(
            content=content,
            latency_ms=latency_ms,
            provider=self._provider_name,
            model=self._model_name,
            input_len=len(user_message),
            output_len=len(content),
        )

    @staticmethod
    def _is_rate_limit(llm_response: LLMResponse) -> bool:
        if getattr(llm_response, "error_code", None) == RATE_LIMIT:
            return True
        detail = str(llm_response.error or "").lower()
        return "rate_limit_exceeded" in detail or "429" in detail

    def _handle_provider_error(
        self, llm_response: LLMResponse, llm_messages: list, user_message: str
    ) -> ChatResponse:
        if self._is_rate_limit(llm_response):
            self.logger.warning(
                f"rate limit on {self._provider_name}: {llm_response.error}"
            )
            retry = self._try_fallback_providers(llm_messages, user_message)
            if retry is not None:
                return retry
            return self._fallback(
                "Too much traffic right now — give it a second and try that again.",
                llm_response.latency_ms,
                user_message,
            )

        return self._fallback(
            "Can't reach the AI right now — give it another go.",
            llm_response.latency_ms,
            user_message,
        )

    def _try_fallback_providers(
        self, llm_messages: list, user_message: str
    ) -> ChatResponse | None:
        from .providers.factory import list_providers

        current = self._provider_name.lower()
        for next_name in (p for p in list_providers() if p != current):
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
                    continue
                self.provider = alt
                self._provider_name = next_name
                self._model_name = alt.get_model_name()
                self.logger.info(f"switched to {next_name} after error")
                self.flow_engine.add_turn(user_message, resp.content)
                self.save_session()
                return self._build_response(resp.content, resp.latency_ms, user_message)
            except Exception as e:
                self.logger.error(f"fallback to {next_name} failed: {e}")
        return None

    def _fallback(
        self, message: str, latency_ms: float, user_message: str
    ) -> ChatResponse:
        # error turns are logged but don't advance the FSM
        self.flow_engine.conversation_history.append(
            {"role": "user", "content": user_message}
        )
        self.flow_engine.conversation_history.append(
            {"role": "assistant", "content": message}
        )
        return self._build_response(message, latency_ms, user_message)

    def _maybe_enrich_with_search(
        self, user_message: str, objection_data: dict | None = None
    ) -> str | None:
        """Run a search and return an appended system-prompt block, or None."""
        if not self.ws_config.get("enabled"):
            return None

        now = time.time()
        min_gap = self.ws_config.get(
            "min_seconds_between_searches", MIN_SECONDS_BETWEEN_SEARCHES
        )
        if now - self.last_search_time < min_gap:
            return None

        stage = str(self.flow_engine.current_stage)
        objection_type = None
        if stage == "objection" and isinstance(objection_data, dict):
            objection_type = objection_data.get("type")

        if not should_trigger_web_search(
            stage, objection_type, user_message, self.ws_config
        ):
            return None

        query = build_search_query(
            objection_type=objection_type,
            product_type=self.product_type or "",
            templates=self.ws_config.get("query_templates", {}),
        )

        response = self.web_search.search(
            query, max_results=self.ws_config.get("max_results", MAX_SEARCH_RESULTS)
        )
        if response.error or not response.results:
            return None

        self.last_search_time = now

        if self.session_id:
            SessionAnalytics.record_web_search(
                session_id=self.session_id,
                query=query,
                result_count=len(response.results),
                cached=response.cached,
            )

        snippets = "\n".join(f"- {r.snippet}" for r in response.results if r.snippet)
        return (
            "\n\n[WEB SEARCH CONTEXT — external validation only, do not quote URLs directly]\n"
            f"{snippets}\n"
            "[Use this to support your reframe. Integrate naturally. Do not present as the primary argument.]\n"
        )

    def _detect_and_switch_strategy(self, user_message) -> bool:
        """Inspect signals to detect and switch strategy. Returns True if switch occurred."""
        user_text = (user_message or "").lower()
        has_cons_user = contains_nonnegated_keyword(
            user_text, _USER_CONSULTATIVE_SIGNALS
        )
        has_trans_user = contains_nonnegated_keyword(
            user_text, _USER_TRANSACTIONAL_SIGNALS
        )

        if has_cons_user:
            self.flow_engine.switch_strategy(Strategy.CONSULTATIVE)
            return True
        elif has_trans_user:
            self.flow_engine.switch_strategy(Strategy.TRANSACTIONAL)
            return True
        elif self.flow_engine.stage_turn_count >= MIN_TURNS_BEFORE_ADVANCE:
            self.flow_engine.switch_strategy(Strategy.CONSULTATIVE)
            return True
        return False

    def _apply_advancement(self, user_message: str) -> None:
        """Check and apply FSM stage advancement. Handles discovery -> real strategy switch."""
        if self.flow_engine.flow_type == Strategy.INTENT:
            old_strategy = self.flow_engine.flow_type
            if self._detect_and_switch_strategy(user_message):
                # Record strategy switch from INTENT to real strategy
                if self.session_id and old_strategy != self.flow_engine.flow_type:
                    SessionAnalytics.record_strategy_switch(
                        session_id=self.session_id,
                        from_strategy=str(old_strategy),
                        to_strategy=str(self.flow_engine.flow_type),
                        reason="signal_detection",
                        user_turn_count=self.flow_engine.user_turn_count,
                    )
                return

        old_stage = self.flow_engine.current_stage
        target_stage = self.flow_engine.get_advance_target(user_message)
        if target_stage:
            self.flow_engine.advance(target_stage=target_stage)

            # Record stage transition
            if self.session_id and old_stage != self.flow_engine.current_stage:
                SessionAnalytics.record_stage_transition(
                    session_id=self.session_id,
                    from_stage=str(old_stage),
                    to_stage=str(self.flow_engine.current_stage),
                    strategy=str(self.flow_engine.flow_type),
                    user_turns_in_stage=self.flow_engine.stage_turn_count - 1,
                )

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

    def rewind(self, steps: int):
        """Rewind back by `steps` turns from the current position."""
        current_turns = len(self.flow_engine.conversation_history) // 2
        return self.rewind_to_turn(max(0, current_turns - steps))

    def rewind_to_turn(self, turn_index: int) -> bool:
        """Rewind to turn_index by hard-resetting FSM state and replaying history."""
        max_turns = len(self.flow_engine.conversation_history) // 2
        if turn_index < 0 or turn_index > max_turns:
            self.logger.warning(f"Invalid turn_index {turn_index}, max is {max_turns}")
            return False

        history_length = turn_index * 2
        if history_length > len(self.flow_engine.conversation_history):
            return False

        old_history = self.flow_engine.conversation_history[:history_length]

        self.flow_engine.reset_to_initial()

        if turn_index == 0:
            return True

        for user_msg_dict, bot_msg_dict in zip(old_history[::2], old_history[1::2]):
            user_msg = user_msg_dict.get("content", "")
            bot_msg = bot_msg_dict.get("content", "")
            self.flow_engine.add_turn(user_msg, bot_msg)
            self._apply_advancement(user_msg)

        return True

    def replay(self, history: list[dict[str, str]]) -> None:
        """Replay a history list into a fresh bot, including strategy-switch detection.

        Use this instead of flow_engine.replay_history() — it applies _apply_advancement
        so intent → consultative/transactional switches are correctly reconstructed.
        """
        for user_msg_dict, bot_msg_dict in zip(history[::2], history[1::2]):
            user_msg = user_msg_dict.get("content", "")
            bot_msg = bot_msg_dict.get("content", "")
            self.flow_engine.add_turn(user_msg, bot_msg)
            self._apply_advancement(user_msg)

    def get_conversation_summary(self):
        """Return FSM state summary with provider info."""
        summary = self.flow_engine.get_summary()
        summary.update({"provider": self._provider_name, "model": self._model_name})
        return summary

    def save_session(self):
        """Persist session state to disk using SessionPersistence.

        Uses the atomic, validated writer in `session_persistence.py` so
        filepaths are checked and writes are atomic.
        """
        if not self.session_id:
            return
        try:
            success = SessionPersistence.save(
                session_id=self.session_id,
                product_type=self.product_type,
                provider_type=self.provider_type,
                flow_type=self.flow_engine.flow_type,
                current_stage=self.flow_engine.current_stage,
                stage_turn_count=self.flow_engine.stage_turn_count,
                conversation_history=self.flow_engine.conversation_history,
                initial_flow_type=self.flow_engine.initial_flow_type,
            )
            if not success:
                self.logger.warning(
                    "Failed to persist session %s via SessionPersistence",
                    self.session_id,
                )
        except Exception as e:
            self.logger.exception("Exception while saving session %s: %s", self.session_id, e)

    def record_session_end(self):
        """Record session completion for evaluation analytics."""
        if not self.session_id:
            return
        # Session events (start, stage transitions, strategy switches) are
        # recorded throughout the conversation lifecycle via SessionAnalytics.

    @staticmethod
    def load_session(session_id):
        """Load session from disk if exists. Returns SalesChatbot or None."""
        try:
            path = f"sessions/{session_id}.json"
            if not os.path.exists(path):
                return None
            with open(path, "r") as f:
                state = json.load(f)
            bot = SalesChatbot(
                provider_type=state.get("provider_type"),
                product_type=state.get("product_type"),
                session_id=session_id,
            )
            bot.flow_engine.restore_state(state)
            return bot
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to load session {session_id}: {e}"
            )
            return None
