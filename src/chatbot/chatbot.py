"""Sales chatbot orchestrator — FSM flow management, LLM calls, performance tracking."""

import json
import logging
import re
import time
from dataclasses import dataclass

from .config_loader import get_product_settings
from .flow import SalesFlowEngine
from .performance import PerformanceTracker
from .providers import create_provider

logger = logging.getLogger(__name__)

# Strategy detection keywords — used by _apply_advancement() discovery mode
_TRANSACTIONAL_INDICATORS = [
    "budget", "price", "cost", "money", "afford",
    "spec", "feature", "delivery", "availability",
]
_CONSULTATIVE_INDICATORS = [
    "help you with", "understand", "transformation",
    "goals", "challenges", "situation", "approach", "strategy",
]

# User-intent cues should dominate strategy choice while in discovery mode
_USER_CONSULTATIVE_SIGNALS = [
    "mentor", "mentorship", "coaching", "coach", "consulting",
    "guidance", "training", "program", "service", "improve", "learn",
]
_USER_TRANSACTIONAL_SIGNALS = [
    "budget", "price", "cost", "buy", "purchase", "order",
    "spec", "feature", "availability", "delivery", "quote",
]


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

    # --- Properties ---

    @property
    def _provider_name(self):
        return type(self.provider).__name__.replace("Provider", "").lower()

    @property
    def _model_name(self):
        return self.provider.get_model_name()

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
        stage = self.flow_engine.current_stage
        flow_type = self.flow_engine.flow_type
        sequence = (
            "intent -> logical -> emotional -> pitch -> objection"
            if flow_type == "consultative"
            else "intent -> pitch -> objection"
        )

        system_prompt = (
            "You are a sales training coach observing a live roleplay session. "
            "Give the trainee concise, specific coaching after each exchange.\n\n"
            f"CONTEXT:\n"
            f"- Strategy: {flow_type} | Stage: {stage} (turn {self.flow_engine.stage_turn_count})\n"
            f"- Stage sequence: {sequence}\n\n"
            "Reply ONLY with valid JSON — no markdown fences, no extra text:\n"
            "{\n"
            '  "stage_goal": "<15 words max: what this stage is trying to accomplish>",\n'
            '  "what_bot_did": "<15 words max: technique the rep just used and why>",\n'
            '  "where_heading": "<15 words max: where the conversation goes next>",\n'
            '  "next_trigger": "<15 words max: what needs to happen to advance>",\n'
            '  "watch_for": ["<tip 1, 10 words max>", "<tip 2, 10 words max>"]\n'
            "}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Prospect: {user_msg}\nSales Rep: {bot_reply}"},
        ]

        try:
            llm_response = self.provider.chat(messages, temperature=0.3, max_tokens=150, stage=stage)
            if llm_response.error or not llm_response.content:
                raise ValueError("Empty or error response")

            raw = llm_response.content.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            result = json.loads(raw)
            if not isinstance(result.get("watch_for"), list):
                result["watch_for"] = []
            return result

        except Exception as e:
            logger.warning(f"Training generation failed: {e}")
            return {
                "stage_goal": f"Progress through the {stage} stage.",
                "what_bot_did": "—",
                "where_heading": "—",
                "next_trigger": "—",
                "watch_for": [],
            }

    def answer_training_question(self, question):
        """Answer a trainee's question about the current conversation and sales techniques."""
        history = self.flow_engine.conversation_history
        stage = self.flow_engine.current_stage
        flow_type = self.flow_engine.flow_type

        recent = history[-10:] if history else []
        conversation_summary = "\n".join(
            f"{'Prospect' if m['role'] == 'user' else 'Sales Rep'}: {m['content'][:100]}"
            for m in recent
        )

        system_prompt = (
            "You are a sales training coach. A trainee is watching a live roleplay and has a question.\n\n"
            f"CONVERSATION CONTEXT:\n"
            f"- Strategy: {flow_type} | Stage: {stage}\n"
            f"- Recent exchange:\n{conversation_summary}\n\n"
            "Reply with 2-3 bullet points using '• ' as the bullet character. "
            "Each bullet: one sentence, max 15 words, actionable and specific to this conversation. "
            "No intro sentence, no summary — bullets only."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        try:
            llm_response = self.provider.chat(messages, temperature=0.4, max_tokens=200, stage=stage)
            if llm_response.error or not llm_response.content:
                return {"answer": "Couldn't generate an answer right now. Try rephrasing your question."}
            return {"answer": llm_response.content.strip()}
        except Exception as e:
            logger.warning(f"Training Q&A failed: {e}")
            return {"answer": "Something went wrong generating the answer. Try again."}

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

    def switch_provider(self, provider_type, model=None):
        """Hot-swap LLM provider without losing conversation state."""
        old_name = self._provider_name
        old_model = self._model_name
        try:
            new_provider = create_provider(provider_type, model=model)
            if not new_provider.is_available():
                return {"success": False, "error": f"{provider_type} provider is not available",
                        "current_provider": old_name, "current_model": old_model}
            self.provider = new_provider
            logger.info(f"Provider switched: {old_name}({old_model}) -> {self._provider_name}({self._model_name})")
            return {"success": True, "from": old_name, "to": provider_type,
                    "old_model": old_model, "new_model": self._model_name}
        except Exception as e:
            logger.error(f"Provider switch failed: {e}")
            return {"success": False, "error": str(e),
                    "current_provider": old_name, "current_model": old_model}
