"""Prospect mode: Bot plays a buyer for sales practice roleplay training."""

import json
import logging
import random
import secrets
import time
from dataclasses import dataclass, field

from .analytics.session_analytics import SessionAnalytics
from .constants import LLM
from .loader import load_prospect_config, load_real_objections
from .buyer_prompt import build_product_context, build_system_prompt
from .buyer_rules import ObjectionPacer, end_outcome
from .real_calls import pick_bank
from .response_guardrails import check_buyer_reply
from .services.provider_router import ProviderRouter
from .selling_quality import (
    NEGATIVE_SIGNALS,
    apply_readiness,
    load_selling_signals,
    score_seller_turn,
)
from .session_review import build_review

logger = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    """Every LLM provider failed or came back empty, so there is no buyer to talk to."""


@dataclass
class BuyerState:
    """Represents the current state of a prospect in a sales roleplay session."""

    readiness: float
    objections_raised: int = 0
    turn_count: int = 0
    has_committed: bool = False
    has_walked: bool = False
    persona: dict = field(default_factory=dict)
    difficulty: str = "medium"
    product_type: str = "default"

    def to_dict(self) -> dict:
        """Convert the state to a dictionary representation."""
        return {
            "readiness": round(self.readiness, 3),
            "objections_raised": self.objections_raised,
            "turn_count": self.turn_count,
            "has_committed": self.has_committed,
            "has_walked": self.has_walked,
            "difficulty": self.difficulty,
            "product_type": self.product_type,
            "persona_name": self.persona.get("name", "Unknown"),
        }

    @property
    def status(self) -> str:
        """Return the session status: 'sold', 'walked', or 'active'."""
        if self.has_committed:
            return "sold"
        if self.has_walked:
            return "walked"
        return "active"


@dataclass
class BuyerResponse:
    """Response from the prospect in a turn of the conversation."""

    content: str
    latency_ms: float
    provider: str
    model: str
    state_snapshot: dict
    coaching: dict | None = None


def personas_for(product_type: str) -> list[dict]:
    """The buyer personas available for a product (its own, else the general pool)."""
    personas = load_prospect_config()["personas"]
    return personas.get(product_type) or personas["general"]


def select_persona(product_type: str, name: str | None = None) -> dict:
    """The named persona for this product, or a random one when no name is given.

    Raises ValueError for a name that is not in this product's pool.
    """
    pool = personas_for(product_type)
    if not name:
        return random.choice(pool)
    for persona in pool:
        if persona["name"].lower() == name.strip().lower():
            return persona
    raise ValueError(f"Unknown persona '{name}' for product '{product_type}'")


class BuyerSession:
    """Manages a prospect-mode conversation for sales roleplay training.

    The session simulates a buyer (prospect) with evolving readiness to purchase
    and tracks the salesperson's performance throughout the conversation.
    """

    def __init__(
        self,
        provider_type: str | None = None,
        product_type: str = "default",
        difficulty: str = "medium",
        persona: dict | None = None,
        session_id: str = "",
        objection: str | None = None,
    ):
        """Initialize a prospect session.

        Args:
            provider_type: LLM provider to use (default: backend-selected order).
            product_type: Type of product being sold (default: 'default').
            difficulty: Session difficulty level (default: 'medium').
            persona: Optional persona dict; randomly selected if None.
            session_id: Optional session identifier.
            objection: Optional objection the learner wants to practise; raised on turn 1.
        """
        # An id-less session saves nothing, logs nothing, and shares its objection
        # dice with every other id-less session. One owner of the id, never blank.
        self.session_id = session_id or secrets.token_hex(16)
        self._router = ProviderRouter(provider_type=provider_type)

        config = load_prospect_config()
        mode_cfg = config.get("prospect_mode", {}) if isinstance(config, dict) else {}
        self.max_turns = int(mode_cfg.get("max_turns", 0) or 0) or None
        self.scoring_enabled = bool(mode_cfg.get("scoring_enabled", True))
        self.feedback_style = str(mode_cfg.get("feedback_style", "coaching") or "coaching")
        profiles = config.get("difficulty_profiles", {})

        if difficulty not in profiles:
            difficulty = "medium"
        self.difficulty_profile = profiles[difficulty]
        behaviour = self.difficulty_profile["behaviour"]
        # Real objections from recorded calls when built; the profile's own bank otherwise.
        profile_bank = self.difficulty_profile.get("objection_bank", [])
        real_pool = load_real_objections()
        self.pacer = ObjectionPacer(
            self.session_id,
            behaviour,
            pick_bank(real_pool, self.session_id, len(profile_bank)) if real_pool else profile_bank,
            first={"type": "chosen", "text": objection} if objection else None,
        )

        if persona is None:
            persona = select_persona(product_type)
        self.persona = persona

        self.product_type = product_type
        self.product_context = build_product_context(product_type, persona)

        self.state = BuyerState(
            readiness=behaviour["initial_readiness"],
            persona=persona,
            difficulty=difficulty,
            product_type=product_type,
        )

        self.conversation_history: list[dict] = []
        # Why the buyer last warmed up or cooled off, for the session review.
        self.last_turn_score = None

        behaviour_rules = config.get("behaviour_rules", {})
        self.behaviour_rules = behaviour_rules.get(difficulty, "")

        # Counted at the start as well as the end, or the two can never be
        # compared and "did anyone finish?" stays unanswerable.
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_start",
            engine="prospect",
            difficulty=difficulty,
            product_type=product_type,
            persona_name=persona.get("name", "Alex"),
        )

    def public_config(self) -> dict:
        """Return the frontend-facing prospect mode settings for this session."""
        return {
            "max_turns": self.max_turns,
            "scoring_enabled": self.scoring_enabled,
            "feedback_style": self.feedback_style,
        }

    @property
    def provider(self):
        return self._router.provider

    @property
    def provider_name(self) -> str:
        return self._router.provider_name

    @property
    def model_name(self) -> str:
        return self._router.model_name

    def _get_chat_with_fallback(self, messages, temperature, max_tokens):
        """Ask the buyer's AI provider, falling back to others on failure.

        Raises ProviderUnavailable when no provider produced anything. Returning the
        empty response instead showed the learner a blank bubble and an HTTP 200,
        which looks like the buyer ignoring them rather than an outage.
        """
        result = self._router.chat_with_fallback(
            messages, temperature=temperature, max_tokens=max_tokens
        )
        if not result.ok:
            error = result.response.error or "empty response"
            logger.error("No provider answered (last=%s): %s", self.provider_name, error)
            raise ProviderUnavailable(result.response.error or "No provider returned a reply.")
        return result.response

    def to_dict(self) -> dict:
        """Serialize enough state to recover the session after a reload."""
        return {
            "session_id": self.session_id,
            "provider_type": self.provider_name,
            "product_type": self.product_type,
            "difficulty": self.state.difficulty,
            "persona": self.persona,
            "conversation_history": self.conversation_history,
            "state": {
                "readiness": self.state.readiness,
                "turn_count": self.state.turn_count,
                "has_committed": self.state.has_committed,
                "has_walked": self.state.has_walked,
            },
        }

    def save_session(self) -> None:
        """Log a compact snapshot of the prospect session."""
        if not self.session_id:
            return
        logger.info(
            "prospect_session_state %s",
            json.dumps(
                {
                    "session_id": self.session_id,
                    "difficulty": self.state.difficulty,
                    "turn_count": self.state.turn_count,
                    "message_count": len(self.conversation_history),
                },
                ensure_ascii=False,
            ),
        )

    def get_opening_message(self) -> BuyerResponse:
        """The prospect's opening line, filled from opening_lines in config (no AI).

        Returns:
            BuyerResponse with the opening message and state snapshot.
        """
        persona = self.persona
        background = str(persona.get("background", "")).strip()
        lines = load_prospect_config()["opening_lines"][self.state.difficulty]
        line = random.Random(self.session_id or "").choice(lines)
        content = line.format(
            name=persona.get("name", "Alex"),
            background=background[:1].lower() + background[1:],
            background_cap=background,
            need=(persona.get("needs") or ["this"])[0],
        )
        latency = 0.0
        self.conversation_history.append(
            {
                "role": "assistant",
                "content": content,
            }
        )
        self._log_turn_event(None, content, turn_index=0)
        self.save_session()

        return BuyerResponse(
            content=content,
            latency_ms=round(latency, 1),
            provider=self.provider_name,
            model=self.model_name,
            state_snapshot=self.state.to_dict(),
        )

    def process_turn(
        self, user_message: str, show_hints: bool = False
    ) -> BuyerResponse:
        """Process a salesperson message and return the prospect's response.

        Args:
            user_message: The salesperson's message in this turn.
            show_hints: If True, generate an optional coaching hint for the user.

        Returns:
            BuyerResponse with prospect's reply, latency and state snapshot.
        """
        if self.state.has_committed or self.state.has_walked:
            return BuyerResponse(
                content=self._terminal_outcome_message(),
                latency_ms=0.0,
                provider=self.provider_name,
                model=self.model_name,
                state_snapshot=self.state.to_dict(),
            )

        if self.max_turns is not None and self.state.turn_count >= self.max_turns:
            # Hard cap: don't accept more turns once max is reached.
            self.state.has_walked = True
            terminal_content = self._terminal_outcome_message()
            self.conversation_history.append({"role": "assistant", "content": terminal_content})
            self.save_session()
            return BuyerResponse(
                content=terminal_content,
                latency_ms=0.0,
                provider=self.provider_name,
                model=self.model_name,
                state_snapshot=self.state.to_dict(),
            )

        # If no provider answers, this turn must leave no trace. Otherwise resending
        # the same line counts it twice and the transcript keeps a seller turn the
        # buyer never replied to - which the review would then replay as real.
        before_turn = (
            self.state.turn_count,
            self.state.readiness,
            self.state.objections_raised,
            len(self.conversation_history),
            self.last_turn_score,
        )
        self.state.turn_count += 1

        self.conversation_history.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        # Update readiness and outcomes before generation so the response matches end state.
        self._update_readiness(user_message)

        session_outcome = end_outcome(
            self.state.readiness,
            self.state.turn_count,
            self.difficulty_profile["behaviour"],
            self.max_turns,
        )
        if session_outcome == "sold":
            self.state.has_committed = True
        elif session_outcome == "walked":
            self.state.has_walked = True

        if self.state.has_committed or self.state.has_walked:
            terminal_content = self._terminal_outcome_message()
            self.conversation_history.append(
                {
                    "role": "assistant",
                    "content": terminal_content,
                }
            )
            self.save_session()
            return BuyerResponse(
                content=terminal_content,
                latency_ms=0.0,
                provider=self.provider_name,
                model=self.model_name,
                state_snapshot=self.state.to_dict(),
            )

        objection = self.pacer.for_turn(self.state.turn_count)
        self.state.objections_raised = self.pacer.raised_by(self.state.turn_count - 1)

        system_prompt = self._system_prompt()
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)

        start = time.time()
        try:
            response = self._get_chat_with_fallback(messages, **LLM["buyer_reply"])
        except ProviderUnavailable:
            self._restore(before_turn)
            raise
        latency = (time.time() - start) * 1000

        if objection:
            self.state.objections_raised += 1

        # LAYER 3: the buyer's words pass the same kind of check as the seller's.
        checked = check_buyer_reply(response.content, self.state.turn_count)
        if checked.applied_rules:
            logger.info("buyer reply checks applied: %s", ", ".join(checked.applied_rules))
        reply = checked.content
        # The rules own objections: the AI answers the seller, then the scripted
        # concern is added word for word, so it always comes after an answer.
        if objection:
            reply = f"{reply} {objection['text']}"

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": reply,
            }
        )
        self._log_turn_event(user_message, reply, turn_index=self.state.turn_count)
        self.save_session()

        # Optional coaching hint
        coaching = None
        if show_hints and not self.state.has_committed and not self.state.has_walked:
            coaching = self._generate_coaching_hint(user_message)

        return BuyerResponse(
            content=reply,
            latency_ms=round(latency, 1),
            provider=self.provider_name,
            model=self.model_name,
            state_snapshot=self.state.to_dict(),
            coaching=coaching,
        )

    def _terminal_outcome_message(self) -> str:
        """Return stable terminal message that matches the current session outcome."""
        if self.state.has_committed:
            return "You've addressed what I needed. I'm ready to move forward."
        if self.state.has_walked:
            if self.max_turns is not None and self.state.turn_count >= self.max_turns:
                return "Time's up for this roleplay. Let's stop here."
            return "I don't think this is the right fit for me right now."
        return "This roleplay session has ended."

    def rewind_to_turn(self, turn_index: int) -> bool:
        """Put the session back to just before turn `turn_index` was sent.

        This is what lets a learner redo a turn and get a real reply from the same
        buyer at the same point, instead of being told what they should have said.
        The buyer's readiness is replayed from the kept transcript rather than
        remembered, so a rewound session is identical to one that had gone that way
        from the start.

        Returns False when that turn does not exist.
        """
        if turn_index < 1:
            return False
        seller_turns = [
            position
            for position, entry in enumerate(self.conversation_history)
            if entry.get("role") == "user"
        ]
        if turn_index > len(seller_turns):
            return False

        self.conversation_history = self.conversation_history[: seller_turns[turn_index - 1]]
        replay = self.review()
        self.state.turn_count = replay["summary"]["turn_count"]
        self.state.objections_raised = self.pacer.raised_by(self.state.turn_count)
        self.state.readiness = replay["readiness_exact"]
        self.state.has_committed = False
        self.state.has_walked = False
        self.last_turn_score = None
        self.save_session()
        return True

    def redo(self, turn_index: int, user_message: str) -> BuyerResponse | None:
        """Rewind to turn `turn_index` and send `user_message` in its place.

        Returns None when that turn does not exist. If the buyer is never reached,
        every rewound turn is put back and the error is raised, so a failed redo
        costs the learner nothing.
        """
        kept = (
            list(self.conversation_history),
            self.state.turn_count,
            self.state.readiness,
            self.state.objections_raised,
            self.state.has_committed,
            self.state.has_walked,
            self.last_turn_score,
        )
        if not self.rewind_to_turn(turn_index):
            return None
        try:
            return self.process_turn(user_message)
        except Exception:
            (
                self.conversation_history,
                self.state.turn_count,
                self.state.readiness,
                self.state.objections_raised,
                self.state.has_committed,
                self.state.has_walked,
                self.last_turn_score,
            ) = kept
            raise

    def _system_prompt(self) -> str:
        """The buyer's instructions for this turn."""
        return build_system_prompt(
            load_prospect_config().get("system_prompt_template", ""),
            persona=self.persona,
            behaviour=self.difficulty_profile["behaviour"],
            readiness=self.state.readiness,
            objections_raised=self.state.objections_raised,
            turn_count=self.state.turn_count,
            product_type=self.product_type,
            product_context=self.product_context,
            behaviour_rules=self.behaviour_rules,
        )

    def _restore(self, snapshot: tuple) -> None:
        """Undo a turn that never reached the buyer."""
        (
            self.state.turn_count,
            self.state.readiness,
            self.state.objections_raised,
            history_length,
            self.last_turn_score,
        ) = snapshot
        del self.conversation_history[history_length:]

    def review(self) -> dict:
        """The walkable review of this session, rebuilt from the transcript."""
        return build_review(self.conversation_history, self.difficulty_profile["behaviour"])

    def _last_buyer_message(self) -> str:
        """The buyer's most recent line, used to tell listening apart from luck."""
        for entry in reversed(self.conversation_history):
            if entry.get("role") == "assistant":
                return entry.get("content", "")
        return ""

    def _update_readiness(self, user_msg: str) -> None:
        """Move the buyer's readiness based on how the salesperson just sold.

        Judged by core.selling_quality, which reads seller language. The reasons
        behind the rating are kept on `last_turn_score` so the session review can
        show the learner why the buyer warmed up or cooled off.
        """
        behaviour = self.difficulty_profile["behaviour"]

        self.last_turn_score = score_seller_turn(
            user_msg,
            buyer_message=self._last_buyer_message(),
            completed_turns=max(0, self.state.turn_count - 1),
        )
        rating = self.last_turn_score.rating

        self.state.readiness = apply_readiness(self.state.readiness, rating, behaviour)

    def _generate_coaching_hint(self, user_message: str) -> dict:
        """One-line tip for the seller, picked from selling_signals.yaml hints (no AI).

        Uses the signals this turn's score already found: the first problem wins,
        then the first strength, then the default line.
        """
        hints = load_selling_signals()["hints"]
        fired = self.last_turn_score.signals if self.last_turn_score else []
        ordered = [s for s in NEGATIVE_SIGNALS if s in fired] + [
            s for s in fired if s not in NEGATIVE_SIGNALS
        ]
        key = next((s for s in ordered if s in hints), "default")
        return {"hint": hints[key]}

    def _log_turn_event(
        self, user_message: str | None, assistant_message: str, turn_index: int
    ) -> None:
        """Emit the full prospect exchange to the application log."""

        if not self.session_id:
            return

        payload = {
            "session_id": self.session_id,
            "turn_index": turn_index,
            "difficulty": self.state.difficulty,
            "product_type": self.product_type,
            "current_readiness": round(self.state.readiness, 3),
            "user_message": user_message,
            "assistant_message": assistant_message,
            "persona_name": self.persona.get("name", "Alex"),
        }
        logger.info("prospect_conversation_turn %s", json.dumps(payload, ensure_ascii=False))

    def record_session_end(self) -> None:
        """Record where this session actually got to.

        Sessions were counted at the start and never at the end, so there was no
        way to tell whether anyone finished one, let alone improved.
        """
        if not self.session_id:
            return
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_end",
            engine="prospect",
            outcome=self.state.status,
            difficulty=self.state.difficulty,
            product_type=self.product_type,
            turn_count=self.state.turn_count,
            objections_raised=self.state.objections_raised,
            final_readiness=round(self.state.readiness, 3),
        )

    def get_evaluation(self) -> dict:
        """Generate a final evaluation of the salesperson's performance.

        Returns:
            Dictionary containing scores, grades, feedback and assessment.
        """
        from .prospect_evaluator import evaluate_prospect_session

        return evaluate_prospect_session(self.conversation_history, self.state)
