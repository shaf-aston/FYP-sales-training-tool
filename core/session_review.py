"""Rebuild a walkable review of a finished practice session.

Nothing is stored for this. The judge in selling_quality is deterministic, so the
whole review - every turn's rating, the reasons behind it, and the buyer's
readiness as it moved - is recomputed from the transcript. That means a review
works on any session that was ever saved, and it can never drift away from what
the learner actually saw, because both come from the same two functions.
"""

from __future__ import annotations

from .selling_quality import NEGATIVE_SIGNALS, REASONS, apply_readiness, load_selling_signals, score_seller_turn


def _pairs(conversation_history: list[dict]) -> list[tuple[str, str]]:
    """Walk the transcript as (what the seller said, how the buyer replied)."""
    pairs, pending = [], None
    for entry in conversation_history or []:
        role, content = entry.get("role"), entry.get("content", "")
        if role == "user":
            if pending is not None:
                pairs.append((pending, ""))
            pending = content
        elif role == "assistant" and pending is not None:
            pairs.append((pending, content))
            pending = None
    if pending is not None:
        pairs.append((pending, ""))
    return pairs


def _opening_buyer_line(conversation_history: list[dict]) -> str:
    """The buyer's opening line, which the seller's first turn responds to."""
    for entry in conversation_history or []:
        if entry.get("role") == "assistant":
            return entry.get("content", "")
        if entry.get("role") == "user":
            return ""
    return ""


def build_review(
    conversation_history: list[dict],
    behaviour: dict,
) -> dict:
    """Annotate every turn of a session and pick out the ones that decided it.

    Args:
        conversation_history: the saved role/content transcript.
        behaviour: the difficulty profile's behaviour block, so the replayed
            readiness matches the difficulty the session was actually played on.

    Returns a dict of `turns`, `pivotal_turns` (turn numbers), `readiness_curve`
    and `summary`. Every turn carries the reasons behind its rating, so no number
    is ever shown without the evidence for it.
    """
    readiness = behaviour.get("initial_readiness", 0.5)
    previous_buyer_line = _opening_buyer_line(conversation_history)
    turns, curve = [], [round(readiness, 3)]

    for index, (seller_line, buyer_reply) in enumerate(_pairs(conversation_history)):
        score = score_seller_turn(
            seller_line, buyer_message=previous_buyer_line, completed_turns=index
        )
        before = readiness
        readiness = apply_readiness(readiness, score.rating, behaviour)
        turns.append(
            {
                "turn": index + 1,
                "seller": seller_line,
                "buyer": buyer_reply,
                "buyer_before": previous_buyer_line,
                "rating": score.rating,
                "signals": score.signals,
                "reasons": score.reasons,
                "readiness_before": round(before, 3),
                "readiness_after": round(readiness, 3),
                "readiness_change": round(readiness - before, 3),
            }
        )
        curve.append(round(readiness, 3))
        previous_buyer_line = buyer_reply or previous_buyer_line

    pivotal = pick_pivotal_turns(turns)
    return {
        "turns": turns,
        "pivotal_turns": pivotal,
        "readiness_curve": curve,
        # The curve is rounded for display. A rewind must restore the exact value
        # live play was carrying, or redoing a turn nudges the buyer a fraction
        # closer to (or further from) buying than it should.
        "readiness_exact": readiness,
        "summary": summarise(turns, pivotal),
    }


def pick_pivotal_turns(turns: list[dict], count: int | None = None) -> list[int]:
    """The turns worth redoing: the ones that cost the most ground.

    Ranked by how far readiness fell, then by how weak the turn was. Turns that
    went well are never offered for a redo - there is nothing to learn from
    replaying a turn that worked.
    """
    limits = load_selling_signals()["thresholds"]
    count = count or limits["pivotal_turns"]
    costly = [t for t in turns if t["readiness_change"] < 0 or t["rating"] <= limits["weak_rating"]]
    costly.sort(key=lambda t: (t["readiness_change"], t["rating"]))
    return sorted(t["turn"] for t in costly[:count])


def _work_on(turns: list[dict]) -> str:
    """The one thing to practise: the most repeated misstep, else the missing habit."""
    seen = [sig for t in turns for sig in t["signals"] if sig in NEGATIVE_SIGNALS]
    if seen:
        return REASONS[max(sorted(set(seen)), key=seen.count)]
    return "Ask more open questions built on the buyer's own words."


def summarise(turns: list[dict], pivotal: list[int] | None = None) -> dict:
    """Headline counts for the top of the review.

    `went_well` is the only licence to praise the session: the average rating
    must clear the configured bar and no turn may have cost ground. `work_on`
    says what to practise otherwise.
    """
    if not turns:
        return {"turn_count": 0, "average_rating": 0.0, "strongest_turn": None, "weakest_turn": None,
                "went_well": False, "work_on": ""}
    ratings = [t["rating"] for t in turns]
    average = round(sum(ratings) / len(ratings), 2)
    bar = load_selling_signals().get("thresholds", {}).get("praise_min_average", 3.5)
    return {
        "turn_count": len(turns),
        "average_rating": average,
        "strongest_turn": max(turns, key=lambda t: t["rating"])["turn"],
        "weakest_turn": min(turns, key=lambda t: t["rating"])["turn"],
        "went_well": average >= bar and not pivotal,
        "work_on": _work_on(turns),
    }
