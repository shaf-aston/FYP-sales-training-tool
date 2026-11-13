"""What the sell-mode buyer does this turn, decided by rules before anything is worded.

  share     answer the question and open up a little (their need, their pain, their budget ...)
  guard     answer, but hold back: they don't trust the seller yet
  stall     don't move forward: not convinced, or pushed too hard
  ask       interested enough to ask how it works
  lean_in   warming up: interested in what was just said

The objection pacer (buyer_rules.ObjectionPacer) adds the turn's objection after the reply, as before; the move is
what comes first. Readiness, the seller's last line (its turn_rating signals) and whether it asked anything decide
the move; thresholds in config/buyer.yaml `moves`. Same inputs, same move: a replayed session goes the same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from core.infra.loader import load_buyer_config, load_yaml
from core.training.turn_rating import load_turn_rating

MOVES = ("share", "guard", "stall", "ask", "lean_in")


@dataclass(frozen=True)
class Move:
    kind: str       # one of MOVES
    topic: str      # what the seller asked about (prospect_lines.yaml `topics`), "next_step", "pressure" or "general"
    objection: bool = False   # the pacer adds an objection after the reply
    closed: bool = False      # the seller asked a yes/no question: "Maybe, depends" fits, "Bits and pieces" doesn't

    @property
    def label(self) -> str:
        """For logs and the review: "share:pain", "stall:pressure+object"."""
        return f"{self.kind}:{self.topic}" + ("+object" if self.objection else "")


def _phrase_at(phrase: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}", text) is not None


def topic_of(line: str) -> str:
    """What the seller's line asks about: the topic in prospect_lines.yaml whose phrase in it is longest (the most
    specific: "how long has" is the pain, "how long" the timeline), the first listed on a tie, else "general". A
    phrase matches a whole word or its start ("frustrat" -> "frustrated")."""
    text = (line or "").lower()
    best, best_len = "general", 0
    for topic, phrases in load_yaml("prospect_lines.yaml")["topics"].items():
        longest = max((len(p) for p in phrases if _phrase_at(p, text)), default=0)
        if longest > best_len:
            best, best_len = topic, longest
    return best


def is_closed(line: str) -> bool:
    """A yes/no question: it opens with "would", "is", "can" ... (or "so would ..."), not "what" or "how"."""
    words = re.findall(r"[a-z']+", (line or "").lower().split("?")[0].split(".")[-1].split("!")[-1])
    words = words[1:] if words[:1] in (["so"], ["and"], ["ok"], ["okay"], ["right"]) else words
    return bool(words) and words[0] in load_buyer_config()["moves"]["closed_openers"]


def asks_to_commit(line: str) -> bool:
    """The seller asked them to take a next step, as a yes/no question ("Shall we book a walkthrough?")."""
    text = (line or "").lower()
    return "?" in text and is_closed(text) and any(_phrase_at(p, text) for p in load_buyer_config()["moves"]["next_step"])


def states_price(line: str) -> bool:
    """The seller told them the price ("It's four thousand for the year.", "The investment is $4,000.")."""
    text = (line or "").lower()
    return "?" not in text and re.search(load_buyer_config()["moves"]["price_said"], text) is not None


def next_move(readiness: float, seller_line: str, signals: list[str], objection: bool = False) -> Move:
    """The buyer's move for this turn.

    - The seller pushed (a pressure or premature-pitch signal): stall, whatever the readiness.
    - The seller asked what questions they have: ask one.
    - The seller asked them to take a next step ("Shall we book a walkthrough?"): keen buyers lean in and say yes,
      the others stall.
    - The seller asked something: share once they are warm enough, else guard. An open question built on what they
      said earns a share while they are still on the fence.
    - The seller told them something: keen buyers lean in, the ones on the fence ask how it works, cold ones stall;
      told the price, each reacts to the price.
    """
    cfg = load_buyer_config()["moves"]
    line = (seller_line or "").lower()
    if any(s in signals for s in cfg["push_back_on"]):
        return Move("stall", "pressure", objection)
    if any(phrase in line for phrase in cfg["invite_questions"]):
        return Move("ask", "general", objection)
    # "Tell me more about that." asks as surely as a question mark does (turn_rating.yaml invitations): taken as a
    # statement, it got "That's fair. Tell me more." back (live, 12 Nov)
    asked = "?" in line or any(_phrase_at(p, line) for p in load_turn_rating()["invitations"])
    closed = "?" in line and is_closed(line)
    warm, cold = readiness >= cfg["open_from"], readiness < cfg["guarded_below"]
    if asks_to_commit(line):
        return Move("lean_in" if warm else "stall", "next_step", objection, closed)
    topic = topic_of(seller_line) if asked else "general"
    if asked:
        earned = "open_question" in signals and "on_topic" in signals
        return Move("share" if warm or (earned and not cold) or (not cold and topic != "general") else "guard",
                     topic, objection, closed)
    # a price they were just told gets a reaction to the price: "I like the sound of that." to "It's four thousand
    # for the year." read as if they had not heard it (live, 13 Nov)
    return Move("lean_in" if warm else "stall" if cold else "ask", "price" if states_price(line) else "general",
                objection)
