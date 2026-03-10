"""Sales chatbot orchestrator — FSM flow management, LLM calls, performance tracking."""

import json
import logging
import re
import time
from dataclasses import dataclass

from .config_loader import get_product_settings, load_signals
from .flow import SalesFlowEngine
from .performance import PerformanceTracker
from .providers import create_provider
from . import trainer

logger = logging.getLogger(__name__)

# Load strategy detection keywords from config
_SIGNALS = load_signals()
_TRANSACTIONAL_INDICATORS = _SIGNALS.get("transactional_bot_indicators", [])
_CONSULTATIVE_INDICATORS = _SIGNALS.get("consultative_bot_indicators", [])
_USER_CONSULTATIVE_SIGNALS = _SIGNALS.get("user_consultative_signals", [])
_USER_TRANSACTIONAL_SIGNALS = _SIGNALS.get("user_transactional_signals", [])


@dataclass
class ChatResponse:
    """Structured response from chat() including latency metrics."""
    content: str
    latency_ms: float = None
    provider: str = None
    model: str = None
    input_len: int = 0
    output_len: int = 0


class SalesChatbot:
    """Orchestrates provider, FSM flow engine, and performance tracking."""

    def __init__(self, provider_type=None, model=None, product_type=None, session_id=None):
        self.provider = create_provider(provider_type, model=model)
        self.session_id = session_id
        
        # Cache provider info to avoid repeated lookups
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
        except ImportError:
            pass

        self.flow_engine = SalesFlowEngine(
            flow_type=config["strategy"],
            product_context=product_context,
        )

    # --- Core chat loop ---

    def chat(self, user_message):
        """Process user message and return ChatResponse with content + metrics."""
        recent_history = self.flow_engine.conversation_history[-10:]
        llm_messages = [
            {"role": "system", "content": self.flow_engine.get_current_prompt(user_message)}
        ] + recent_history + [
            {"role": "user", "content": user_message}
        ]

        request_start = time.time()
        try:
            llm_response = self.provider.chat(
                llm_messages,
                temperature=0.8,
                max_tokens=200,
                stage=self.flow_engine.current_stage,
            )

            if llm_response.error or not llm_response.content:
                error_detail = llm_response.error or "empty response"
                return self._fallback(
                    f"I'm having trouble ({error_detail}). Try again?",
                    llm_response.latency_ms, user_message,
                )

            bot_reply = llm_response.content
            self.flow_engine.add_turn(user_message, bot_reply)

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

            return ChatResponse(
                content=bot_reply,
                latency_ms=llm_response.latency_ms,
                provider=self._provider_name,
                model=self._model_name,
                input_len=len(user_message),
                output_len=len(bot_reply),
            )

        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return self._fallback(
                "Something went wrong. Can you try again?",
                (time.time() - request_start) * 1000, user_message,
            )

    def _fallback(self, message, latency_ms, user_message):
        """Build fallback ChatResponse after adding turn to history."""
        self.flow_engine.add_turn(user_message, message)
        return ChatResponse(
            content=message,
            latency_ms=latency_ms,
            provider=self._provider_name,
            model=self._model_name,
            input_len=len(user_message),
            output_len=len(message),
        )

    def _apply_advancement(self, user_message):
        """Check and apply FSM stage advancement. Handles discovery -> real strategy switch."""
        from .analysis import text_contains_any_keyword

        if self.flow_engine.flow_type == "intent":
            history = self.flow_engine.conversation_history
            user_text = (user_message or "").lower()
            has_cons_user = text_contains_any_keyword(user_text, _USER_CONSULTATIVE_SIGNALS)
            has_trans_user = text_contains_any_keyword(user_text, _USER_TRANSACTIONAL_SIGNALS)

            if has_cons_user:
                self.flow_engine.switch_strategy("consultative")
            elif has_trans_user:
                self.flow_engine.switch_strategy("transactional")
            elif len(history) >= 2:
                bot_last = history[-1].get("content", "").lower()
                has_trans = text_contains_any_keyword(bot_last, _TRANSACTIONAL_INDICATORS)
                has_cons = text_contains_any_keyword(bot_last, _CONSULTATIVE_INDICATORS)

                if has_cons:
                    self.flow_engine.switch_strategy("consultative")
                elif has_trans:
                    self.flow_engine.switch_strategy("transactional")
                elif self.flow_engine.stage_turn_count >= 3:
                    self.flow_engine.switch_strategy("consultative")

        advancement = self.flow_engine.should_advance(user_message)
        if advancement:
            self.flow_engine.advance(
                target_stage=advancement if isinstance(advancement, str) else None
            )

    # --- Training ---

    def generate_training(self, user_msg, bot_reply):
        """Generate coaching notes for the current exchange via lightweight LLM call."""
        return trainer.generate_training(self.provider, self.flow_engine, user_msg, bot_reply)

    def answer_training_question(self, question):
        """Answer a trainee's question about the current conversation and sales techniques."""
        return trainer.answer_training_question(self.provider, self.flow_engine, question)

    # --- Session management ---

    def rewind_to_turn(self, turn_index):
        """Rewind to turn_index by hard-resetting FSM state and replaying history."""
        max_turns = len(self.flow_engine.conversation_history) // 2
        if turn_index < 0 or turn_index > max_turns:
            logger.warning(f"Invalid turn_index {turn_index}, max is {max_turns}")
            return False

        history_length = turn_index * 2
        if history_length > len(self.flow_engine.conversation_history):
            return False

        old_history = self.flow_engine.conversation_history[:history_length]
        if old_history and history_length % 2 != 0:
            logger.warning("Invalid history slice (odd length)")
            return False

        self.flow_engine.conversation_history = []
        self.flow_engine.stage_turn_count = 0
        self.flow_engine.current_stage = self.flow_engine.flow_config["stages"][0]
        self.flow_engine.replay_history(old_history)
        return True

    def get_conversation_summary(self):
        """Return FSM state summary with provider info."""
        summary = self.flow_engine.get_summary()
        summary.update({"provider": self._provider_name, "model": self._model_name})
        return summary
