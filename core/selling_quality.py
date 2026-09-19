"""Judge one salesperson turn on what the seller actually did.

Every rule here reads SELLER language. The older keyword lists in
config/signals.yaml describe BUYER language and must not be used on a seller's
message - a seller asking "are you interested?" is not a buying signal.

Each fired rule carries a plain-English reason so the post-session review can
show the learner why a turn was marked the way it was, rather than a bare number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import load_yaml
from .utils import contains_nonnegated_keyword, tokenize

NEUTRAL_RATING = 3.0

REASONS = {
    "open_question": "Asked an open question that invites them to explain.",
    "mirroring": "Used the buyer's own words back to them - shows you were listening.",
    "acknowledgement": "Acknowledged what they said before moving on.",
    "pressure": "Used urgency or scarcity language, which reads as pushy.",
    "premature_pitch": "Talked commercials before finding out what they care about.",
    "question_stacking": "Asked several questions at once, so none get a real answer.",
    "monologue": "Long enough that the buyer stops reading.",
    "low_effort": "Too short to move the conversation anywhere.",
}


@dataclass(frozen=True)
class SellerTurnScore:
    """A 1-5 rating plus the evidence behind it."""

    rating: int
    signals: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"rating": self.rating, "signals": list(self.signals), "reasons": list(self.reasons)}


def load_selling_signals() -> dict:
    """Load the seller-language rules. Falls back to an empty config."""
    return load_yaml("selling_signals.yaml") or {}


def _asks_open_question(message: str, openers) -> bool:
    if "?" not in message:
        return False
    lowered = message.lower()
    return any(re.search(rf"\b{re.escape(opener)}\b", lowered) for opener in openers)


def _mirrored_words(message: str, buyer_message: str, stopwords) -> list[str]:
    """Distinct content words the seller echoed back from the buyer's last message."""
    if not buyer_message:
        return []
    ignore = {w.lower() for w in stopwords}
    buyer_words = {w for w in tokenize(buyer_message) if len(w) > 2 and w not in ignore}
    seller_words = {w for w in tokenize(message) if len(w) > 2 and w not in ignore}
    return sorted(buyer_words & seller_words)


def score_seller_turn(
    message: str,
    buyer_message: str = "",
    completed_turns: int = 0,
    config: dict | None = None,
) -> SellerTurnScore:
    """Rate one salesperson message from 1 (poor) to 5 (strong).

    Args:
        message: what the salesperson just said.
        buyer_message: the buyer's previous message, used to detect listening and
            to tell an answer about price apart from an unprompted pitch.
        completed_turns: turns finished before this one, so early pitching can be
            told apart from pitching once discovery has happened.
        config: parsed selling_signals.yaml; loaded when omitted.
    """
    cfg = config if config is not None else load_selling_signals()
    weights = cfg.get("weights", {})
    limits = cfg.get("thresholds", {})

    text = message or ""
    words = text.split()
    fired: list[str] = []

    if _asks_open_question(text, cfg.get("open_question_openers", [])):
        fired.append("open_question")

    overlap = _mirrored_words(text, buyer_message, cfg.get("mirroring_stopwords", []))
    if len(overlap) >= limits.get("mirroring_min_overlap", 2):
        fired.append("mirroring")

    if contains_nonnegated_keyword(text.lower(), cfg.get("acknowledgement", [])):
        fired.append("acknowledgement")

    if contains_nonnegated_keyword(text.lower(), cfg.get("pressure", [])):
        fired.append("pressure")

    # Commercial talk is only premature when the buyer has not raised it themselves.
    pitch_words = cfg.get("pitch_language", [])
    if completed_turns < limits.get("discovery_turns", 2):
        seller_pitched = contains_nonnegated_keyword(text.lower(), pitch_words)
        buyer_asked = contains_nonnegated_keyword((buyer_message or "").lower(), pitch_words)
        if seller_pitched and not buyer_asked:
            fired.append("premature_pitch")

    if text.count("?") >= limits.get("question_stacking_count", 3):
        fired.append("question_stacking")

    if len(words) > limits.get("monologue_words", 90):
        fired.append("monologue")
    elif len(words) < limits.get("low_effort_words", 4):
        fired.append("low_effort")

    total = NEUTRAL_RATING + sum(weights.get(name, 0.0) for name in fired)
    rating = max(1, min(5, round(total)))
    return SellerTurnScore(
        rating=rating,
        signals=fired,
        reasons=[REASONS[name] for name in fired if name in REASONS],
    )
