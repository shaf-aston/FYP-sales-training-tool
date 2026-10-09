"""The buyer's rules: when they object, and when the session ends.

Pure logic, no AI calls, no I/O. BuyerSession asks; this module answers.
"""

import random

from .constants import SOLD_MIN_TURNS, SOLD_READINESS, WALK_MIN_TURNS, WALK_READINESS
from .selling_quality import NEGATIVE_SIGNALS, load_turn_rating


class ObjectionPacer:
    """Decides which turns the buyer pushes back on, and with what.

    The difficulty profile says how often (objection_probability) and how many
    times (max_objections); the bank says what about. Every answer is derived
    from the session id and turn number, never stored, so replaying or rewinding
    a session always gives the same objections on the same turns.
    """

    def __init__(self, session_id: str, behaviour: dict, bank: list[dict], first: dict | None = None):
        """`first` is an objection the learner chose to practise: raised on turn 1, every time."""
        self.session_id = session_id
        self.probability = float(behaviour.get("objection_probability", 0.0))
        self.first = first
        self.bank = [first, *bank] if first else bank
        cap = int(behaviour.get("max_objections", 0))
        self.cap = min(max(cap, 1) if first else cap, len(self.bank))

    def dice(self, turn: int) -> float:
        """A fixed roll for one turn of this session."""
        return random.Random(f"{self.session_id}|{turn}").random()

    def _fires(self, turn: int) -> bool:
        """True when this turn's roll (or the chosen first objection) calls for one."""
        return (self.first is not None and turn == 1) or self.dice(turn) < self.probability

    def raised_by(self, turn: int) -> int:
        """How many objections were issued up to and including `turn`."""
        raised = 0
        for past_turn in range(1, max(0, turn) + 1):
            if raised >= self.cap:
                break
            if self._fires(past_turn):
                raised += 1
        return raised

    def for_turn(self, turn: int) -> dict | None:
        """The objection to raise on `turn`, or None."""
        already = self.raised_by(turn - 1)
        if already >= self.cap or not self._fires(turn):
            return None
        return self.bank[already]


def end_outcome(readiness: float, turn_count: int, behaviour: dict) -> str | None:
    """'sold', 'walked', or None while the conversation should go on."""
    if readiness >= SOLD_READINESS and turn_count >= SOLD_MIN_TURNS:
        return "sold"
    if turn_count >= behaviour["patience_turns"] and readiness < WALK_READINESS:
        return "walked"
    if readiness <= 0.0 and turn_count >= WALK_MIN_TURNS:
        return "walked"
    return None


def coaching_hint(turn_score) -> dict:
    """One-line tip for the seller, picked from turn_rating.yaml hints (no AI).

    Uses the signals the turn's score already found: the first problem wins,
    then the first strength, then the default line.
    """
    hints = load_turn_rating()["hints"]
    fired = turn_score.signals if turn_score else []
    ordered = [s for s in NEGATIVE_SIGNALS if s in fired] + [s for s in fired if s not in NEGATIVE_SIGNALS]
    key = next((s for s in ordered if s in hints), "default")
    return {"hint": hints[key]}
