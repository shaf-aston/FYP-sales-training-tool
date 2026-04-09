"""Main chatbot class. Wires together the provider, flow engine, and analytics."""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from .loader import get_product_settings, load_signals, assign_ab_variant, load_web_search_config
from .analysis import text_contains_any_keyword, classify_objection, should_trigger_web_search, build_search_query, analyze_state
from .web_search import WebSearchService
from .flow import SalesFlowEngine
from .analytics.performance import PerformanceTracker
from .analytics.session_analytics import SessionAnalytics
from .session_persistence import SessionPersistence
from .providers import create_provider
from .utils import Strategy, Stage
from .training import trainer
from .constants import (
    RECENT_HISTORY_WINDOW,
    MIN_SECONDS_BETWEEN_SEARCHES,
    SEARCH_CACHE_TTL_SECONDS,
    MAX_SEARCH_RESULTS,
    MIN_TURNS_BEFORE_STRATEGY_FALLBACK,
    DEFAULT_TEMPERATURE,
    DEFAULT_MAX_TOKENS,
)

_base_logger = logging.getLogger(__name__)

_PROVIDER_FALLBACK_ORDER = ["sambanova", "groq"]
_MSG_RATE_LIMITED = "Getting a lot of traffic right now — give it a second and try again."
_MSG_PROVIDER_DOWN = "I'm having trouble connecting right now. Please try again."


def _format_search_context(results) -> str:
    """Format search results into a prompt-injectable block."""
    snippets = "\n".join(f"- {r.snippet}" for r in results if r.snippet)
    return (
        "\n\n[WEB SEARCH CONTEXT — external validation only, do not quote URLs directly]\n"
        f"{snippets}\n"
        "[Use this to support your reframe. Integrate naturally. Do not present as the primary argument.]\n"
    )


# Load strategy detection keywords from config
_SIGNALS = load_signals()
_TRANSACTIONAL_INDICATORS = _SIGNALS.get("transactional_bot_indicators", [])
_CONSULTATIVE_INDICATORS = _SIGNALS.get("consultative_bot_indicators", [])
_USER_CONSULTATIVE_SIGNALS = _SIGNALS.get("user_consultative_signals", [])
_USER_TRANSACTIONAL_SIGNALS = _SIGNALS.get("user_transactional_signals", [])


@dataclass
class ChatResponse:
    content: str
    latency_ms: float | None = None  # ms, None if provider didn't report
    provider: str | None = None
    model: str | None = None
    input_len: int = 0
    output_len: int = 0


class SalesChatbot:
    """Orchestrates provider, FSM flow engine, and performance tracking."""

    def __init__(self, provider_type=None, model=None, product_type=None, session_id=None):
        self.provider = create_provider(provider_type, model=model)
        self.session_id = session_id
        self.product_type = product_type
        self.provider_type = provider_type
        self.logger = logging.LoggerAdapter(_base_logger, {"session_id": session_id or "-"})

        # grab these once so we're not calling into the provider on every turn
        self._provider_name = type(self.provider).__name__.replace("Provider", "").lower()
        self._model_name = self.provider.get_model_name()

        config = get_product_settings(product_type or "")

        product_context = config["context"]
        if "knowledge" in config:
            product_context = f"{config['context']}\n\nPRODUCT KNOWLEDGE:\n{config['knowledge']}"

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
            _base_logger.debug(f"skipping custom knowledge: {e}")

        self.flow_engine = SalesFlowEngine(
            flow_type=config["strategy"],
            product_context=product_context,
        )

        # Web search enrichment service + config
        self._ws_config = load_web_search_config()
        self._web_search = WebSearchService(cache_ttl=self._ws_config.get("cache_ttl_seconds", SEARCH_CACHE_TTL_SECONDS))
        self._last_search_time: float = 0.0

        # A/B variant assignment for prompt testing (deterministic per session)
        self._ab_variant = assign_ab_variant(session_id) if session_id else None

        # Record session start for evaluation analytics
        if session_id:
            SessionAnalytics.record_session_start(
                session_id=session_id,
                product_type=product_type or "unknown",
                initial_strategy=str(self.flow_engine.flow_type),
                ab_variant=self._ab_variant
            )

    def _try_switch_to_provider(self, new_provider_type: str) -> bool:
        """Attempt to switch to a fallback provider mid-session."""
        try:
            new_provider = create_provider(new_provider_type)
            if new_provider.is_available():
                self.provider = new_provider
                self.provider_type = new_provider_type
                self._provider_name = type(self.provider).__name__.replace("Provider", "").lower()
                self._model_name = self.provider.get_model_name()
                self.logger.info(f"switched to fallback provider: {new_provider_type}")
                return True
            else:
                self.logger.warning(f"Fallback provider {new_provider_type} is not available (missing keys?).")
                return False
        except Exception as e:
            self.logger.error(f"Failed to switch to provider {new_provider_type}: {e}")
            return False

    def chat(self, user_message: str) -> ChatResponse:
        """Process user message and return ChatResponse with content + metrics."""
        recent_history = self.flow_engine.conversation_history[-RECENT_HISTORY_WINDOW:]

        state = analyze_state(self.flow_engine.conversation_history, user_message)

        objection_data = None
        if self.flow_engine.current_stage == Stage.OBJECTION:
            objection_data = classify_objection(user_message, self.flow_engine.conversation_history)

        # Assemble system prompt, then optionally append search context
        system_prompt = self.flow_engine.get_current_prompt(user_message, objection_data=objection_data, pre_state=state)
        search_context = self._maybe_enrich_with_search(user_message, objection_data=objection_data)
        if search_context:
            system_prompt += search_context

        llm_messages = [
            {"role": "system", "content": system_prompt}
        ] + recent_history + [
            {"role": "user", "content": user_message}
        ]

        if self.session_id:
            SessionAnalytics.record_intent_classification(
                session_id=self.session_id,
                intent_level=state.intent,
                user_turn_count=self.flow_engine.user_turn_count + 1,
            )

        request_start = time.time()
        
        fallbacks = list(_PROVIDER_FALLBACK_ORDER)
        if self._provider_name in fallbacks:
            fallbacks.remove(self._provider_name)
        providers_to_try = [self._provider_name] + fallbacks

        llm_response = None
        error_detail = "empty response"

        try:
            for provider_name in providers_to_try:
                if provider_name != self._provider_name:
                    if not self._try_switch_to_provider(provider_name):
                        continue
                        
                llm_response = self.provider.chat(
                    llm_messages,
                    temperature=DEFAULT_TEMPERATURE,
                    max_tokens=DEFAULT_MAX_TOKENS,
                    stage=self.flow_engine.current_stage,
                )

                if not llm_response.error and llm_response.content:
                    break  # Success!
                
                error_detail = llm_response.error or "empty response"
                self.logger.warning(f"Provider {provider_name} failed: {error_detail}")

            if not llm_response or llm_response.error or not llm_response.content:
                if "rate_limit_exceeded" in str(error_detail).lower() or "429" in str(error_detail):
                    self.logger.warning(f"Rate limit hit globally: {error_detail}")
                    return self._fallback(
                        _MSG_RATE_LIMITED,
                        llm_response.latency_ms if llm_response else 0, user_message,
                    )
                else:
                    return self._fallback(
                        _MSG_PROVIDER_DOWN,
                        llm_response.latency_ms if llm_response else 0, user_message,
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
                    provider=self._provider_name,
                    model=self._model_name,
                    user_message_length=len(user_message),
                    bot_response_length=len(bot_reply),
                )

            self._apply_advancement(user_message)

            # Record objection classification if at OBJECTION stage
            if self.session_id and self.flow_engine.current_stage == Stage.OBJECTION and objection_data:
                objection_type = objection_data.get("type", "unknown") if isinstance(objection_data, dict) else "unknown"
                user_turn_count = self.flow_engine.user_turn_count
                SessionAnalytics.record_objection_classified(
                    session_id=self.session_id,
                    objection_type=objection_type,
                    strategy=str(self.flow_engine.flow_type),
                    user_turn_count=user_turn_count
                )

            return ChatResponse(
                content=bot_reply,
                latency_ms=llm_response.latency_ms,
                provider=self._provider_name,
                model=self._model_name,
                input_len=len(user_message),
                output_len=len(bot_reply),
            )

        except Exception:
            self.logger.exception("Unexpected error")
            return self._fallback(
                "Something went wrong. Can you try again?",
                (time.time() - request_start) * 1000, user_message,
            )

    def _fallback(self, message: str, latency_ms: float, user_message: str) -> ChatResponse:
        """Builds fallback response and logs the turn. Error turns skip FSM advancement."""
        self.flow_engine.conversation_history.append({"role": "user", "content": user_message})
        self.flow_engine.conversation_history.append({"role": "assistant", "content": message})
        return ChatResponse(
            content=message,
            latency_ms=latency_ms,
            provider=self._provider_name,
            model=self._model_name,
            input_len=len(user_message),
            output_len=len(message),
        )

    def _maybe_enrich_with_search(self, user_message: str, objection_data: dict | None = None) -> str | None:
        """Runs web search if conditions are met, returns a formatted context block.
        Falls back silently on any failure — the conversation just continues as-is.
        """
        if not self._ws_config.get("enabled"):
            return None

        now = time.time()
        if now - self._last_search_time < self._ws_config.get("min_seconds_between_searches", MIN_SECONDS_BETWEEN_SEARCHES):
            return None

        stage = str(self.flow_engine.current_stage)

        # skip re-computing objection type if caller already has it
        objection_type = None
        if stage == "objection" and objection_data:
            objection_type = objection_data.get("type") if isinstance(objection_data, dict) else None

        if not should_trigger_web_search(stage, objection_type, user_message, self._ws_config):
            return None

        query = build_search_query(
            objection_type=objection_type,
            product_type=self.product_type or "",
            templates=self._ws_config.get("query_templates", {}),
        )

        response = self._web_search.search(query, max_results=self._ws_config.get("max_results", MAX_SEARCH_RESULTS))

        if response.error or not response.results:
            return None

        self._last_search_time = now

        if self.session_id:
            SessionAnalytics.record_web_search(
                session_id=self.session_id,
                query=query,
                result_count=len(response.results),
                cached=response.cached,
            )

        return _format_search_context(response.results)

    def _detect_and_switch_strategy(self, user_message) -> bool:
        """Inspect signals to detect and switch strategy. Returns True if switch occurred."""
        user_text = (user_message or "").lower()
        has_cons_user = text_contains_any_keyword(user_text, _USER_CONSULTATIVE_SIGNALS)
        has_trans_user = text_contains_any_keyword(user_text, _USER_TRANSACTIONAL_SIGNALS)

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
                        user_turn_count=self.flow_engine.user_turn_count
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
                    user_turns_in_stage=self.flow_engine.stage_turn_count - 1
                )

    def generate_training(self, user_msg: str, bot_reply: str) -> dict[str, Any]:
        """Generate coaching notes for the current exchange via lightweight LLM call."""
        return trainer.generate_training(self.provider, self.flow_engine, user_msg, bot_reply)

    def answer_training_question(self, question: str) -> dict[str, Any]:
        """Answer a trainee's question about the current conversation and sales techniques."""
        return trainer.answer_training_question(self.provider, self.flow_engine, question)

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

        # Reset FSM to initial state (clears history and resets to initial strategy)
        self.flow_engine.reset_to_initial()

        # full reset, nothing to replay
        if turn_index == 0:
            return True

        # Replay history with strategy-switch handling (calls _apply_advancement per turn)
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
        """Persist session state to disk using SessionPersistence."""
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
            initial_flow_type=str(self.flow_engine._initial_flow_type)
        )

    def record_session_end(self):
        """Record session completion for evaluation analytics."""
        if not self.session_id:
            return
        user_turn_count = self.flow_engine.user_turn_count
        bot_turn_count = len(self.flow_engine.conversation_history) - user_turn_count
        SessionAnalytics.record_session_end(
            session_id=self.session_id,
            final_stage=str(self.flow_engine.current_stage),
            final_strategy=str(self.flow_engine.flow_type),
            user_turn_count=user_turn_count,
            bot_turn_count=bot_turn_count
        )

    @staticmethod
    def load_session(session_id):
        """Load session from disk if exists. Returns SalesChatbot or None."""
        state = SessionPersistence.load(session_id)

        if not state:
            return None

        try:
            bot = SalesChatbot(
                provider_type=state.get("provider_type"),
                product_type=state.get("product_type"),
                session_id=session_id
            )
            bot.flow_engine.restore_state(state)
            return bot
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to restore session {session_id}: {e}")
            return None
