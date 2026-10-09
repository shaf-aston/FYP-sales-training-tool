"""Sell mode: the AI plays a buyer and the learner practises selling to it."""

import logging
import random
import time

from .analytics.session_analytics import SessionAnalytics
from .buyer_guardrails import check_buyer_reply
from .buyer_prompt import build_product_context, build_system_prompt
from .buyer_record import BuyerRecord
from .buyer_rules import ObjectionPacer, coaching_hint, end_outcome
from .buyer_state import BuyerResponse, BuyerState, persona_name, select_persona
from .constants import LLM
from .loader import load_buyer_config, load_real_objections
from .real_calls import pick_bank
from .selling_quality import apply_readiness, score_seller_turn
from .services.provider_router import ProviderRouter, ProviderUnavailable, complete
from .session_review import build_review
from .utils import new_session_id

logger = logging.getLogger(__name__)


class BuyerSession(BuyerRecord):
    """One sell-mode conversation: an AI buyer whose readiness to buy moves with how well
    the learner (the salesperson) sells."""

    def __init__(
        self,
        provider_type: str | None = None,
        product_type: str = "default",
        difficulty: str | None = None,
        persona: dict | None = None,
        session_id: str = "",
        objection: str | None = None,
    ):
        """`persona` is picked at random when None; `objection` is one the learner chose to
        practise, raised on turn 1."""
        # An id-less session logs nothing and shares its objection dice with every other
        # id-less session. One owner of the id, never blank.
        self.session_id = session_id or new_session_id()
        self._router = ProviderRouter(provider_type=provider_type)

        config = load_buyer_config()
        profiles = config["difficulty_profiles"]
        if difficulty not in profiles:
            difficulty = config["default_difficulty"]
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

        self.persona = persona if persona is not None else select_persona(product_type)
        self.product_type = product_type
        self.product_context = build_product_context(product_type)

        self.state = BuyerState(
            readiness=behaviour["initial_readiness"],
            persona=self.persona,
            difficulty=difficulty,
            product_type=product_type,
        )

        self.conversation_history: list[dict] = []
        # Why the buyer last warmed up or cooled off, for the session review.
        self.last_turn_score = None
        self.behaviour_rules = config.get("behaviour_rules", {}).get(difficulty, "")

        # Counted at the start as well as the end, or the two can never be
        # compared and "did anyone finish?" stays unanswerable.
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_start",
            mode="sell",
            difficulty=difficulty,
            product_type=product_type,
            persona_name=persona_name(self.persona),
        )

    @property
    def provider_name(self) -> str:
        return self._router.provider_name

    @property
    def model_name(self) -> str:
        return self._router.model_name

    def _response(self, content: str, latency_ms: float = 0.0, coaching: dict | None = None) -> BuyerResponse:
        return BuyerResponse(
            content=content,
            latency_ms=round(latency_ms, 1),
            provider=self.provider_name,
            model=self.model_name,
            state_snapshot=self.state.to_dict(),
            coaching=coaching,
        )

    def get_opening_message(self) -> BuyerResponse:
        """The buyer's opening line, filled from opening_lines in config (no AI)."""
        persona = self.persona
        background = str(persona.get("background", "")).strip()
        lines = load_buyer_config()["opening_lines"][self.state.difficulty]
        line = random.Random(self.session_id).choice(lines)
        content = line.format(
            name=persona_name(persona),
            background=background[:1].lower() + background[1:],
            background_cap=background,
            need=(persona.get("needs") or ["this"])[0],
        )
        self.conversation_history.append({"role": "assistant", "content": content})
        self._log_turn_event(None, content, turn_index=0)
        self.log_snapshot()
        return self._response(content)

    def process_turn(self, user_message: str, show_hints: bool = False) -> BuyerResponse:
        """The salesperson's message in; the buyer's reply out. `show_hints` adds a coaching hint."""
        if self.state.ended:
            return self._response(self._end_message())

        # If no provider answers, this turn must leave no trace. Otherwise resending
        # the same line counts it twice and the transcript keeps a seller turn the
        # buyer never replied to - which the review would then replay as real.
        before_turn = self._snapshot()
        self.state.turn_count += 1
        self.conversation_history.append({"role": "user", "content": user_message})

        # Update readiness and outcomes before generation so the response matches end state.
        self._update_readiness(user_message)
        outcome = end_outcome(self.state.readiness, self.state.turn_count, self.difficulty_profile["behaviour"])
        self.state.has_committed = outcome == "sold"
        self.state.has_walked = outcome == "walked"

        if self.state.ended:
            content = self._end_message()
            self.conversation_history.append({"role": "assistant", "content": content})
            self.log_snapshot()
            return self._response(content)

        objection = self.pacer.for_turn(self.state.turn_count)
        self.state.objections_raised = self.pacer.raised_by(self.state.turn_count - 1)

        messages = [{"role": "system", "content": self._system_prompt()}, *self.conversation_history]
        start = time.time()
        try:
            reply_text = complete(self._router, messages, **LLM["buyer_reply"])
        except ProviderUnavailable:
            self._restore(before_turn)
            raise
        latency = (time.time() - start) * 1000

        if objection:
            self.state.objections_raised += 1

        checked = check_buyer_reply(reply_text, self.state.turn_count)
        if checked.applied_rules:
            logger.info("buyer reply checks applied: %s", ", ".join(checked.applied_rules))
        reply = checked.content
        # The rules own objections: the AI answers the seller, then the scripted
        # concern is added word for word, so it always comes after an answer.
        if objection:
            reply = f"{reply} {objection['text']}"

        self.conversation_history.append({"role": "assistant", "content": reply})
        self._log_turn_event(user_message, reply, turn_index=self.state.turn_count)
        self.log_snapshot()

        coaching = coaching_hint(self.last_turn_score) if show_hints else None
        return self._response(reply, latency, coaching)

    def _end_message(self) -> str:
        """The buyer's fixed last line for how the session ended."""
        return load_buyer_config()["end_messages"][
            "sold" if self.state.has_committed else "walked" if self.state.has_walked else "ended"
        ]

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
        self.log_snapshot()
        return True

    def redo(self, turn_index: int, user_message: str) -> BuyerResponse | None:
        """Rewind to turn `turn_index` and send `user_message` in its place.

        Returns None when that turn does not exist. If the buyer is never reached,
        every rewound turn is put back and the error is raised, so a failed redo
        costs the learner nothing.
        """
        kept = self._snapshot()
        if not self.rewind_to_turn(turn_index):
            return None
        try:
            return self.process_turn(user_message)
        except Exception:
            self._restore(kept)
            raise

    def _snapshot(self) -> tuple:
        """Everything a turn can change, for putting it back with `_restore`."""
        state = self.state
        return (
            list(self.conversation_history),
            state.turn_count,
            state.readiness,
            state.objections_raised,
            state.has_committed,
            state.has_walked,
            self.last_turn_score,
        )

    def _restore(self, snapshot: tuple) -> None:
        state = self.state
        (
            self.conversation_history,
            state.turn_count,
            state.readiness,
            state.objections_raised,
            state.has_committed,
            state.has_walked,
            self.last_turn_score,
        ) = snapshot

    def _system_prompt(self) -> str:
        """The buyer's instructions for this turn."""
        return build_system_prompt(
            load_buyer_config()["system_prompt_template"],
            persona=self.persona,
            readiness=self.state.readiness,
            product_context=self.product_context,
            behaviour_rules=self.behaviour_rules,
        )

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
        """Move the buyer's readiness by how well the salesperson just sold.

        The reasons behind the rating are kept on `last_turn_score` so the session
        review can show the learner why the buyer warmed up or cooled off.
        """
        self.last_turn_score = score_seller_turn(
            user_msg,
            buyer_message=self._last_buyer_message(),
            completed_turns=max(0, self.state.turn_count - 1),
        )
        self.state.readiness = apply_readiness(
            self.state.readiness, self.last_turn_score.rating, self.difficulty_profile["behaviour"]
        )

    def get_evaluation(self) -> dict:
        """Score the salesperson's whole session (rules only)."""
        from .sell_evaluator import evaluate_sell_session

        return evaluate_sell_session(self.conversation_history, self.state)
