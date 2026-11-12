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

MOVES = ("share", "guard", "stall", "ask", "lean_in")


@dataclass(frozen=True)
class Move:
    kind: str       # one of MOVES
    topic: str      # what the seller asked about (prospect_lines.yaml `topics`), "pressure" or "general"
    objection: bool = False   # the pacer adds an objection after the reply

    @property
    def label(self) -> str:
        """For logs and the review: "share:pain", "stall:pressure+object"."""
        return f"{self.kind}:{self.topic}" + ("+object" if self.objection else "")


def topic_of(line: str) -> str:
    """What the seller's line asks about: the first topic in prospect_lines.yaml with a phrase in it, else
    "general". A phrase ending in a letter matches a whole word or its start ("frustrat" -> "frustrated")."""
    text = (line or "").lower()
    for topic, phrases in load_yaml("prospect_lines.yaml")["topics"].items():
        if any(re.search(rf"\b{re.escape(p)}", text) for p in phrases):
            return topic
    return "general"


def next_move(readiness: float, seller_line: str, signals: list[str], objection: bool = False) -> Move:
    """The buyer's move for this turn.

    - The seller pushed (a pressure or premature-pitch signal): stall, whatever the readiness.
    - The seller asked what questions they have: ask one.
    - The seller asked something: share once they are warm enough, else guard. An open question built on what they
      said earns a share while they are still on the fence.
    - The seller told them something: keen buyers lean in, the ones on the fence ask how it works, cold ones stall.
    """
    cfg = load_buyer_config()["moves"]
    if any(s in signals for s in cfg["push_back_on"]):
        return Move("stall", "pressure", objection)
    if any(phrase in (seller_line or "").lower() for phrase in cfg["invite_questions"]):
        return Move("ask", "general", objection)
    asked = "?" in (seller_line or "")
    topic = topic_of(seller_line) if asked else "general"
    warm, cold = readiness >= cfg["open_from"], readiness < cfg["guarded_below"]
    if asked:
        earned = "open_question" in signals and "on_topic" in signals
        return Move("share" if warm or (earned and not cold) or (not cold and topic != "general") else "guard",
                     topic, objection)
    return Move("lean_in" if warm else "stall" if cold else "ask", "general", objection)
