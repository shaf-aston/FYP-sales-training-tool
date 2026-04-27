"""Shared helper utilities used across chatbot modules"""

import json
import re
from bisect import bisect
from enum import Enum
from functools import lru_cache

# frozenset negations are unordered and hashed for O(1) lookup and immutability

DEFAULT_NEGATIONS = frozenset(
    {
        "not",
        "don't",
        "doesn't",
        "no",
        "never",
        "can't",
        "won't",
        "cannot",
        "dont",
        "didnt",
        "didn't",
        "doesnt",
        "cant",
    }
)


@lru_cache(maxsize=512)
def _build_union_pattern_for_keywords(keyword_tuple) -> re.Pattern:
    """Compile one regex that matches any keyword in the given tuple."""
    parts = [rf"\b{re.escape(k)}\b" for k in keyword_tuple]
    return re.compile("|".join(parts), re.IGNORECASE)


def contains_nonnegated_keyword(
    text: str, keywords, negations=None, neg_window: int = 3
) -> bool:
    """Check whether text contains a keyword not negated by nearby words"""
    if not text or not keywords:
        return False

    # normalize keywords to a list
    if isinstance(keywords, str):
        keys = [keywords]
    else:
        keys = list(keywords)
    if not keys:
        return False

    pattern = _build_union_pattern_for_keywords(tuple(keys))
    negset = frozenset(negations) if negations is not None else DEFAULT_NEGATIONS

    for match in pattern.finditer(text):
        preceding_words = re.findall(r"\w+", text[: match.start()])
        if preceding_words:
            window = [w.lower() for w in preceding_words[-neg_window:]]
            if any(w in negset for w in window):
                # appears negated - skip
                continue
        return True
    return False


def clamp_score(value, default=50) -> int:
    """Clamp LLM-returned score to 0–100 int range"""
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp float to [lo, hi]"""
    return max(lo, min(hi, value))


def extract_json_from_llm(content: str) -> dict | None:
    """Extract the first JSON object from LLM response text - falls back to None if parsing fails"""
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def range_label(value, thresholds, labels):
    """Map a numeric value to the label for the threshold band it falls into.

    `thresholds` defines the band boundaries, and `labels` must contain one
    label for each band plus one extra label above the final threshold.
    Example: range_label(85, [60,70,80,90], ["F","D","C","B","A"]) -> "B"
    """
    return labels[bisect(thresholds, value)]


class Strategy(str, Enum):
    CONSULTATIVE = "consultative"
    TRANSACTIONAL = "transactional"
    INTENT = "intent"


class Stage(str, Enum):
    INTENT = "intent"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    PITCH = "pitch"
    NEGOTIATION = "negotiation"
    OBJECTION = "objection"
    OUTCOME = "outcome"


