"""Sell mode: the AI plays a buyer and the learner practises selling to it."""

import logging
import random
import secrets
import time

from .analytics.session_analytics import SessionAnalytics
from .buyer_prompt import build_product_context, build_system_prompt
from .buyer_record import SessionRecord
from .buyer_rules import ObjectionPacer, coaching_hint, end_outcome
from .buyer_state import BuyerResponse, BuyerState, select_persona
from .constants import LLM
from .loader import load_real_objections, load_sell_config
from .real_calls import pick_bank
from .response_guardrails import check_buyer_reply
from .selling_quality import apply_readiness, score_seller_turn
from .services.provider_router import ProviderRouter, ProviderUnavailable, complete
from .session_review import build_review

logger = logging.getLogger(__name__)


class BuyerSession(SessionRecord):
    """Manages a sell-mode conversation for sales roleplay training.

    The session simulates a buyer with evolving readiness to purchase
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
        """Initialize a sell session.

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

        config = load_sell_config()
        mode_cfg = config.get("sell_mode", {}) if isinstance(config, dict) else {}
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
        self.product_context = build_product_context(product_type)

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
            engine="sell",
            difficulty=difficulty,
            product_type=product_type,
            persona_name=persona.get("name", "Alex"),
        )

    def public_config(self) -> dict:
        """Return the frontend-facing sell mode settings for this session."""
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

    def get_opening_message(self) -> BuyerResponse:
        """The buyer's opening line, filled from opening_lines in config (no AI).

        Returns:
            BuyerResponse with the opening message and state snapshot.
        """
        persona = self.persona
        background = str(persona.get("background", "")).strip()
        lines = load_sell_config()["opening_lines"][self.state.difficulty]
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
        """Process a salesperson message and return the buyer's response.

        Args:
            user_message: The salesperson's message in this turn.
            show_hints: If True, generate an optional coaching hint for the user.

        Returns:
            BuyerResponse with the buyer's reply, latency and state snapshot.
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
            reply_text = complete(self._router, messages, **LLM["buyer_reply"])
        except ProviderUnavailable:
            self._restore(before_turn)
            raise
        latency = (time.time() - start) * 1000

        if objection:
            self.state.objections_raised += 1

        # LAYER 3: the buyer's words pass the same kind of check as the seller's.
        checked = check_buyer_reply(reply_text, self.state.turn_count)
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
            coaching = coaching_hint(self.last_turn_score)

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
            load_sell_config().get("system_prompt_template", ""),
            persona=self.persona,
            readiness=self.state.readiness,
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

    def get_evaluation(self) -> dict:
        """Generate a final evaluation of the salesperson's performance.

        Returns:
            Dictionary containing scores, grades, feedback and assessment.
        """
        from .sell_evaluator import evaluate_sell_session

        return evaluate_sell_session(self.conversation_history, self.state)
