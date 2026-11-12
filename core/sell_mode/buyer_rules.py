"""The buyer's rules: when they object, and when the session ends.

Pure logic, no AI calls, no I/O. BuyerSession asks; this module answers.
"""

import random
import re

from core.infra.constants import SOLD_MIN_TURNS, SOLD_READINESS, WALK_MIN_TURNS, WALK_READINESS
from core.training.turn_rating import NEGATIVE_SIGNALS, load_turn_rating


class ObjectionPacer:
    """Decides which turns the buyer pushes back on, and with what.

    The difficulty profile says how often (objection_probability) and how many
    times (max_objections); the bank says what about. Every answer is derived
    from the session id, the turn number and what the seller has said, never stored, so replaying or rewinding
    a session always gives the same objections on the same turns.

    With `said` (the seller's lines so far, one per turn), an objection waits until the call has got to it
    (buyer.yaml `objection_waits`): no "what justifies the premium?" before price or the offer has come up. A turn
    whose roll calls for one raises the first objection in the bank that is ready, or none.
    """

    def __init__(self, session_id: str, behaviour: dict, bank: list[dict], first: dict | None = None,
                 waits: dict | None = None):
        """`first` is an objection the learner chose to practise: raised on turn 1, every time."""
        self.session_id = session_id
        self.probability = float(behaviour.get("objection_probability", 0.0))
        self.first = first
        self.bank = [first, *bank] if first else bank
        cap = int(behaviour.get("max_objections", 0))
        self.cap = min(max(cap, 1) if first else cap, len(self.bank))
        self.waits = waits or {}

    def dice(self, turn: int) -> float:
        """A fixed roll for one turn of this session."""
        return random.Random(f"{self.session_id}|{turn}").random()

    def _fires(self, turn: int) -> bool:
        """True when this turn's roll (or the chosen first objection) calls for one."""
        return (self.first is not None and turn == 1) or self.dice(turn) < self.probability

    def ready(self, objection: dict, turn: int, said: list[str]) -> bool:
        """Whether the call has got far enough for this objection on `turn` (`said`: the seller's lines to it)."""
        wait = self.waits.get(objection.get("type"))
        if not wait:
            return True
        lines = [line.lower() for line in said[:turn]]
        return (
            turn >= wait.get("turn", 10 ** 6)
            or (wait.get("pitch", False) and any(_is_pitch(line) for line in lines))
            or any(re.search(rf"\b{re.escape(word)}", line) for word in wait.get("mention", []) for line in lines)
        )

    def _raised(self, turn: int, said: list[str] | None) -> list[tuple[int, dict]]:
        """(turn, objection) for every objection raised up to and including `turn`."""
        raised: list[tuple[int, dict]] = []
        waiting = list(self.bank)
        for t in range(1, max(0, turn) + 1):
            if len(raised) >= self.cap:
                break
            if not self._fires(t):
                continue
            pick = next((o for o in waiting if said is None or self.ready(o, t, said)), None)
            if pick is not None:
                waiting.remove(pick)
                raised.append((t, pick))
        return raised

    def raised_by(self, turn: int, said: list[str] | None = None) -> int:
        """How many objections were issued up to and including `turn`."""
        return len(self._raised(turn, said))

    def for_turn(self, turn: int, said: list[str] | None = None) -> dict | None:
        """The objection to raise on `turn`, or None."""
        raised = self._raised(turn, said)
        return raised[-1][1] if raised and raised[-1][0] == turn else None


_PITCH_MIN_WORDS = 6


def _is_pitch(line: str) -> bool:
    """The seller told them something (a claim about the offer), rather than asking: no question, a full sentence."""
    return "?" not in line and len(line.split()) >= _PITCH_MIN_WORDS


def end_outcome(readiness: float, turn_count: int, behaviour: dict, asked_to_commit: bool = False) -> str | None:
    """'sold', 'walked', or None while the conversation should go on. A keen buyer says yes only when asked
    (`asked_to_commit`: the seller's line asked for the next step); three good questions are not a sale."""
    if readiness >= SOLD_READINESS and turn_count >= SOLD_MIN_TURNS and asked_to_commit:
        return "sold"
    if turn_count >= behaviour["patience_turns"] and readiness < WALK_READINESS:
        return "walked"
    if readiness <= 0.0 and turn_count >= WALK_MIN_TURNS:
        return "walked"
    return None


def coaching_hint(fired: list[str]) -> dict:
    """One-line tip for the seller, picked from turn_rating.yaml hints (no AI).

    `fired` is the signals the turn already showed: the first problem wins,
    then the first strength, then the default line.
    """
    hints = load_turn_rating()["hints"]
    ordered = [s for s in NEGATIVE_SIGNALS if s in fired] + [s for s in fired if s not in NEGATIVE_SIGNALS]
    key = next((s for s in ordered if s in hints), "default")
    return {"hint": hints[key]}
