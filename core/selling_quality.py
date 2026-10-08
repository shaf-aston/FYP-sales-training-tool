"""Judge one salesperson turn on what the seller actually did.

Every rule here reads SELLER language: a seller asking "are you interested?" is not a
buying signal.

Each fired rule carries a plain-English reason so the post-session review can
show the learner why a turn was marked the way it was, rather than a bare number.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .loader import load_yaml
from .utils import clamp, contains_nonnegated_keyword, tokenize

REASONS = {
    "open_question": "Asked an open question that invites them to explain.",
    "on_topic": "Built the question on something they actually said.",
    "generic_question": "Asked a stock question that could be put to anyone.",
    "closed_question": "Asked a yes-or-no question, which gets a one-word answer.",
    "mirroring": "Used the buyer's own words back to them - shows you were listening.",
    "acknowledgement": "Acknowledged what they said before moving on.",
    "pressure": "Used urgency or scarcity language, which reads as pushy.",
    "premature_pitch": "Talked commercials before finding out what they care about.",
    "question_stacking": "Asked several questions at once, so none get a real answer.",
    "monologue": "Long enough that the buyer stops reading.",
    "low_effort": "Too short to move the conversation anywhere.",
}

# Signals that cost the seller ground.
NEGATIVE_SIGNALS = (
    "pressure", "premature_pitch", "question_stacking", "monologue",
    "low_effort", "generic_question", "closed_question",
)


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


def _sentences(message: str) -> list[str]:
    return [p for p in re.split(r"(?<=[.!?])\s+", message.strip()) if p]


def _has_word(text: str, words) -> bool:
    return any(re.search(rf"\b{re.escape(w)}\b", text) for w in words)


def _count_openings(message: str, question_words, invitations, stock_questions=()) -> int:
    """How many times the seller tried to open the buyer up in one turn.

    Counts each invitation ("walk me through it"), which opens someone up without
    asking a question, plus each sentence that is itself a question using a
    question word. Judged per sentence: a pitch that ends "what do you think?"
    has one open question, not an open turn. Stock questions ("how are you?")
    do not count - they open nothing.
    """
    lowered = message.lower()
    count = sum(len(re.findall(rf"\b{re.escape(p)}\b", lowered)) for p in invitations)
    for sentence in _sentences(lowered):
        if sentence.endswith("?") and _has_word(sentence, question_words) and not _has_word(
            sentence, stock_questions
        ):
            count += 1
    return count


def _is_closed_question(message: str, question_words, closed_starters) -> bool:
    """A question sentence that starts with a yes/no verb and has no question word."""
    for sentence in _sentences(message.lower()):
        first = re.findall(r"[a-z']+", sentence)[:1]
        if sentence.endswith("?") and first and first[0] in closed_starters and not _has_word(
            sentence, question_words
        ):
            return True
    return False


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

    question_words = cfg.get("question_words", [])
    stock = cfg.get("stock_questions", [])
    openings = _count_openings(text, question_words, cfg.get("invitations", []), stock)
    overlap = _mirrored_words(text, buyer_message, cfg.get("mirroring_stopwords", []))
    if openings:
        fired.append("open_question")
        if overlap:
            fired.append("on_topic")
    elif _has_word(text.lower(), stock) and "?" in text:
        fired.append("generic_question")
    elif _is_closed_question(text, question_words, cfg.get("closed_starters", [])):
        fired.append("closed_question")

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

    if openings >= limits.get("question_stacking_count", 3):
        fired.append("question_stacking")

    if len(words) > limits.get("monologue_words", 90):
        fired.append("monologue")
    elif len(words) < limits.get("low_effort_words", 4):
        fired.append("low_effort")

    total = limits["neutral_rating"] + sum(weights.get(name, 0.0) for name in fired)
    rating = max(1, min(5, round(total)))
    return SellerTurnScore(
        rating=rating,
        signals=fired,
        reasons=[REASONS[name] for name in fired if name in REASONS],
    )


def readiness_delta(rating: int, behaviour: dict) -> float:
    """How far a turn of this quality moves the buyer's readiness.

    Kept here so live play and the after-the-fact replay in session_review use the
    same formula - two copies would let a review disagree with what the learner saw.
    """
    gain = behaviour.get("readiness_gain_per_good_turn", 0.0)
    loss = behaviour.get("readiness_loss_per_bad_turn", 0.0)
    if rating >= 4:
        return gain * (rating - 3)  # 4->gain, 5->2*gain
    if rating <= 2:
        return -loss * (3 - rating)  # 2->-loss, 1->-2*loss
    # A turn that neither helps nor hurts still buys a little patience. How much
    # is a difficulty knob, not a constant - a tough buyer should drift less.
    return float(behaviour.get("readiness_drift_per_neutral_turn", 0.01))


def apply_readiness(current: float, rating: int, behaviour: dict) -> float:
    """Readiness after a turn of this quality, clamped to 0-1."""
    return clamp(current + readiness_delta(rating, behaviour))
