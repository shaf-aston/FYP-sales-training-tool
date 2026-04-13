"""main chatbot module"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from . import trainer
from .analysis import analyse_state, build_search_query, classify_objection, should_trigger_web_search
from .analytics.performance import PerformanceTracker
from .analytics.session_analytics import SessionAnalytics
from .constants import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    MAX_SEARCH_RESULTS,
    MIN_SECONDS_BETWEEN_SEARCHES,
    MIN_TURNS_BEFORE_STRATEGY_FALLBACK,
    RECENT_HISTORY_WINDOW,
    SEARCH_CACHE_TTL_SECONDS,
)
from .flow import SalesFlowEngine
from .loader import assign_ab_variant, get_product_settings, loadSIGNALS, load_web_search_config
from .providers import create_provider
from .session_persistence import SessionPersistence
from .utils import Stage, Strategy, contains_nonnegated_keyword
from .web_search import WebSearchService

logger = logging.getLogger(__name__)

PROVIDER_FALLBACK_ORDER = ["sambanova", "groq"]
MSG_RATE_LIMITED = "We're experiencing high traffic — please wait a moment and try again."
MSG_PROVIDER_DOWN = "The provider is currently unreachable — please wait a moment and try again."


SIGNALS = loadSIGNALS()
USER_CONSULTATIVESIGNALS = SIGNALS.get("user_consultativeSIGNALS", [])
USER_TRANSACTIONALSIGNALS = SIGNALS.get("user_transactionalSIGNALS", [])


@dataclass
class ChatResponse:
    content: str
    latency_ms: float | None = None  # ms, None if provider didn't report
    provider: str | None = None
    model: str | None = None
    input_len: int = 0
    output_len: int = 0


class SalesChatbot:
    def __init__(self, provider_type=None, model=None, product_type=None, session_id=None):
        self.provider = create_provider(provider_type, model=model)
        self.session_id = session_id
        self.product_type = product_type
        self.provider_type = provider_type
        self.logger = logging.LoggerAdapter(logger, {"session_id": session_id or "-"})

        self.provider_name = type(self.provider).__name__.replace("Provider", "").lower()
        self.model_name = self.provider.get_model_name()

        config = get_product_settings(product_type or "")

        product_context = config["context"]
        if "knowledge" in config:
            product_context = f"{config['context']}\n\nPRODUCT KNOWLEDGE:\n{config['knowledge']}"

        try:
            from .knowledge import get_custom_knowledge_text

            custom_knowledge = get_custom_knowledge_text()
            if custom_knowledge:
                product_context += (
                    f"\n\n--- BEGIN CUSTOM PRODUCT DATA ---\n{custom_knowledge}\n--- END CUSTOM PRODUCT DATA ---"
                )
        except Exception as e:
            logger.debug(f"skipping custom knowledge: {e}")

        self.flow_engine = SalesFlowEngine(
            flow_type=config["strategy"],
            product_context=product_context,
        )

        self.ws_config = load_web_search_config()
        self.web_search = WebSearchService(cache_ttl=self.ws_config.get("cache_ttl_seconds", SEARCH_CACHE_TTL_SECONDS))
        self.last_search_time: float = 0.0

        self.ab_variant = assign_ab_variant(session_id) if session_id else None

        if session_id:
            SessionAnalytics.record_session_start(
                session_id=session_id,
                product_type=product_type or "unknown",
                initial_strategy=str(self.flow_engine.flow_type),
                ab_variant=self.ab_variant,
            )

    def _try_switch_to_provider(self, new_provider_type: str) -> bool:
        """Try switching to a fallback provider."""
        try:
            new_provider = create_provider(new_provider_type)
            if new_provider.is_available():
                self.provider = new_provider
                self.provider_type = new_provider_type
                self.provider_name = type(self.provider).__name__.replace("Provider", "").lower()
                self.model_name = self.provider.get_model_name()
                self.logger.info(f"switched to fallback provider: {new_provider_type}")
                return True
            else:
                self.logger.warning(f"Fallback provider {new_provider_type} is not available (missing keys?).")
                return False
        except Exception as e:
            self.logger.error(f"Failed to switch to provider {new_provider_type}: {e}")
            return False

    def chat(self, user_message: str) -> ChatResponse:
        """Handle a user message and return a ChatResponse."""
        recent_history = self.flow_engine.conversation_history[-RECENT_HISTORY_WINDOW:]

        state = analyse_state(self.flow_engine.conversation_history, user_message)

        objection_data = None
        # only classify objections at the objection stage
        if str(self.flow_engine.current_stage).lower() == "objection" and user_message:
            objection_data = classify_objection(user_message, self.flow_engine.conversation_history)

        system_prompt = self.flow_engine.get_current_prompt(
            user_message, objection_data=objection_data, pre_state=state
        )
        search_context = self._maybe_enrich_with_search(user_message, objection_data=objection_data)
        if search_context:
            system_prompt += search_context

        llm_messages = (
            [{"role": "system", "content": system_prompt}]
            + recent_history
            + [{"role": "user", "content": user_message}]
        )

        if self.session_id:
            SessionAnalytics.record_intent_classification(
                session_id=self.session_id,
                intent_level=state.intent,
                user_turn_count=self.flow_engine.user_turn_count + 1,
            )

        request_start = time.time()

        fallbacks = list(PROVIDER_FALLBACK_ORDER)
        if self.provider_name in fallbacks:
            fallbacks.remove(self.provider_name)
        providers_to_try = [self.provider_name] + fallbacks

        llm_response = None
        error_detail = "empty response"

        try:
            for prov in providers_to_try:
                if prov != self.provider_name:
                    if not self._try_switch_to_provider(prov):
                        continue

                llm_response = self.provider.chat(
                    llm_messages,
                    temperature=DEFAULT_TEMPERATURE,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    stage=self.flow_engine.current_stage,
                )

                if not llm_response.error and llm_response.content:
                    break

                error_detail = llm_response.error or "empty response"
                self.logger.warning(f"Provider {prov} failed: {error_detail}")

            if not llm_response or llm_response.error or not llm_response.content:
                if "rate_limit_exceeded" in str(error_detail).lower() or "429" in str(error_detail):
                    self.logger.warning(f"Rate limit hit globally: {error_detail}")
                    return self._fallback(
                        MSG_RATE_LIMITED,
                        llm_response.latency_ms if llm_response else 0,
                        user_message,
                    )
                else:
                    return self._fallback(
                        MSG_PROVIDER_DOWN,
                        llm_response.latency_ms if llm_response else 0,
                        user_message,
                    )

            bot_reply = llm_response.content
            self.flow_engine.add_turn(user_message, bot_reply)
            threading.Thread(target=self.save_session, daemon=True).start()

            if self.session_id:
                PerformanceTracker.log_stage_latency(
                    session_id=self.session_id,
                    stage=self.flow_engine.current_stage,
                    strategy=self.flow_engine.flow_type,
                    latency_ms=llm_response.latency_ms,
                    provider=self.provider_name,
                    model=self.model_name,
                    user_message_length=len(user_message),
                    bot_response_length=len(bot_reply),
                )

            self._apply_advancement(user_message)

            if self.session_id and self.flow_engine.current_stage == Stage.OBJECTION and objection_data:
                objection_type = (
                    objection_data.get("type", "unknown") if isinstance(objection_data, dict) else "unknown"
                )
                user_turn_count = self.flow_engine.user_turn_count
                SessionAnalytics.record_objection_classified(
                    session_id=self.session_id,
                    objection_type=objection_type,
                    strategy=str(self.flow_engine.flow_type),
                    user_turn_count=user_turn_count,
                )

            return ChatResponse(
                content=bot_reply,
                latency_ms=llm_response.latency_ms,
                provider=self.provider_name,
                model=self.model_name,
                input_len=len(user_message),
                output_len=len(bot_reply),
            )

        except Exception:
            self.logger.exception("Unexpected error")
            return self._fallback(
                "Sorry — something went awry. Try once more?",
                (time.time() - request_start) * 1000,
                user_message,
            )

    def _fallback(self, message: str, latency_ms: float, user_message: str) -> ChatResponse:
        """Fallback response; log the turn and skip FSM advancement."""
        self.flow_engine.conversation_history.append({"role": "user", "content": user_message})
        self.flow_engine.conversation_history.append({"role": "assistant", "content": message})
        return ChatResponse(
            content=message,
            latency_ms=latency_ms,
            provider=self.provider_name,
            model=self.model_name,
            input_len=len(user_message),
            output_len=len(message),
        )

    def _maybe_enrich_with_search(self, user_message: str, objection_data: dict | None = None) -> str | None:
        """web search if conditions are right"""
        if not self.ws_config.get("enabled"):
            return None

        now = time.time()
        if now - self.last_search_time < self.ws_config.get(
            "min_seconds_between_searches", MIN_SECONDS_BETWEEN_SEARCHES
        ):
            return None

        stage = str(self.flow_engine.current_stage)

        objection_type = None
        if stage == "objection" and objection_data:
            objection_type = objection_data.get("type") if isinstance(objection_data, dict) else None

        if not should_trigger_web_search(stage, objection_type, user_message, self.ws_config):
            return None

        query = build_search_query(
            objection_type=objection_type,
            product_type=self.product_type or "",
            templates=self.ws_config.get("query_templates", {}),
        )

        response = self.web_search.search(query, max_results=self.ws_config.get("max_results", MAX_SEARCH_RESULTS))

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
        """Check user signals and switch strategy if needed."""
        user_text = (user_message or "").lower()
        has_cons_user = contains_nonnegated_keyword(user_text, USER_CONSULTATIVESIGNALS)
        has_trans_user = contains_nonnegated_keyword(user_text, USER_TRANSACTIONALSIGNALS)

        if has_cons_user:
            self.flow_engine.switch_strategy(Strategy.CONSULTATIVE)
            return True
        elif has_trans_user:
            self.flow_engine.switch_strategy(Strategy.TRANSACTIONAL)
            return True
        elif self.flow_engine.stage_turn_count >= MIN_TURNS_BEFORE_STRATEGY_FALLBACK:
            self.flow_engine.switch_strategy(Strategy.CONSULTATIVE)
            return True
        return False

    def _apply_advancement(self, user_message: str) -> None:
        """Check and apply FSM stage advancement."""
        if self.flow_engine.flow_type == Strategy.INTENT:
            old_strategy = Strategy.INTENT
            if self._detect_and_switch_strategy(user_message):
                if self.session_id and old_strategy != Strategy.INTENT:
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

            if self.session_id and old_stage != self.flow_engine.current_stage:
                SessionAnalytics.record_stage_transition(
                    session_id=self.session_id,
                    from_stage=str(old_stage),
                    to_stage=str(self.flow_engine.current_stage),
                    strategy=str(self.flow_engine.flow_type),
                    user_turns_in_stage=self.flow_engine.stage_turn_count - 1,
                )

    def generate_training(self, user_msg: str, bot_reply: str) -> dict[str, Any]:
        """Coaching notes for the current exchange."""
        return trainer.generate_training(self.provider, self.flow_engine, user_msg, bot_reply)

    def answer_training_question(self, question: str) -> dict[str, Any]:
        """Answer a trainee's question about sales techniques."""
        return trainer.answer_training_question(self.provider, self.flow_engine, question)

    def rewind_to_turn(self, turn_index: int) -> bool:
        """Rewind to turn_index by resetting FSM and replaying history."""
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
        """Replay history into a fresh bot with strategy-switch detection."""
        for user_msg_dict, bot_msg_dict in zip(history[::2], history[1::2]):
            user_msg = user_msg_dict.get("content", "")
            bot_msg = bot_msg_dict.get("content", "")
            self.flow_engine.add_turn(user_msg, bot_msg)
            self._apply_advancement(user_msg)

    def get_conversation_summary(self):
        """FSM state summary with provider info."""
        summary = self.flow_engine.get_summary()
        summary.update({"provider": self.provider_name, "model": self.model_name})
        return summary

    def save_session(self):
        """Persist session state to disk."""
        if not self.session_id:
            return

        SessionPersistence.save(
            session_id=self.session_id,
            product_type=self.product_type,
            provider_type=self.provider_type,
            flow_type=str(self.flow_engine.flow_type),
            current_stage=str(self.flow_engine.current_stage),
            stage_turn_count=self.flow_engine.stage_turn_count,
            conversation_history=self.flow_engine.conversation_history,
            initial_flow_type=str(self.flow_engine.initial_flow_type),
        )

    @staticmethod
    def load_session(session_id):
        """Load session from disk if it exists."""
        state = SessionPersistence.load(session_id)

        if not state:
            return None

        try:
            bot = SalesChatbot(
                provider_type=state.get("provider_type"), product_type=state.get("product_type"), session_id=session_id
            )
            bot.flow_engine.restore_state(state)
            return bot
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to restore session {session_id}: {e}")
            return None
