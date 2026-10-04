"""The buyer's rules: when they object, and when the session ends.

Pure logic, no AI calls, no I/O. BuyerSession asks; this module answers.
"""

import random

from .constants import SOLD_MIN_TURNS, SOLD_READINESS, WALK_READINESS


class ObjectionPacer:
    """Decides which turns the buyer pushes back on, and with what.

    The difficulty profile says how often (objection_probability) and how many
    times (max_objections); the bank says what about. Every answer is derived
    from the session id and turn number, never stored, so replaying or rewinding
    a session always gives the same objections on the same turns.
    """

    def __init__(self, session_id: str, behaviour: dict, bank: list[dict]):
        self.session_id = session_id
        self.probability = float(behaviour.get("objection_probability", 0.0))
        self.bank = bank
        self.cap = min(int(behaviour.get("max_objections", 0)), len(bank))

    def dice(self, turn: int) -> float:
        """A fixed roll for one turn of this session."""
        return random.Random(f"{self.session_id}|{turn}").random()

    def raised_by(self, turn: int) -> int:
        """How many objections were issued up to and including `turn`."""
        raised = 0
        for past_turn in range(1, max(0, turn) + 1):
            if raised >= self.cap:
                break
            if self.dice(past_turn) < self.probability:
                raised += 1
        return raised

    def for_turn(self, turn: int) -> dict | None:
        """The objection to raise on `turn`, or None."""
        already = self.raised_by(turn - 1)
        if already >= self.cap or self.dice(turn) >= self.probability:
            return None
        return self.bank[already]


def end_outcome(readiness: float, turn_count: int, behaviour: dict, max_turns: int | None) -> str | None:
    """'sold', 'walked', or None while the conversation should go on."""
    if readiness >= SOLD_READINESS and turn_count >= SOLD_MIN_TURNS:
        return "sold"
    if max_turns is not None and turn_count >= max_turns:
        return "walked"
    if turn_count >= behaviour["patience_turns"] and readiness < WALK_READINESS:
        return "walked"
    if readiness <= 0.0:
        return "walked"
    return None
