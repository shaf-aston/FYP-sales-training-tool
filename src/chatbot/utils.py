"""Shared utilities — extracted to eliminate cross-module duplication."""
import json
import re
from bisect import bisect
from enum import Enum
from functools import lru_cache


# --- Negation-aware keyword matching (shared) ---
_DEFAULT_NEGATIONS = frozenset({
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
})


@lru_cache(maxsize=512)
def _build_union_pattern_for_keywords(keyword_tuple) -> re.Pattern:
    parts = [rf"\b{re.escape(k)}\b" for k in keyword_tuple]
    return re.compile('|'.join(parts), re.IGNORECASE)


def contains_nonnegated_keyword(text: str, keywords, negations=None, neg_window: int = 3) -> bool:
    """True if text contains a keyword not negated in the previous tokens."""
    if not text or not keywords:
        return False

    # Normalize keywords to a list
    if isinstance(keywords, str):
        keys = [keywords]
    else:
        keys = list(keywords)
    if not keys:
        return False

    pattern = _build_union_pattern_for_keywords(tuple(keys))
    negset = frozenset(negations) if negations is not None else _DEFAULT_NEGATIONS

    for match in pattern.finditer(text):
        preceding_words = re.findall(r"\w+", text[: match.start()])
        if preceding_words:
            window = [w.lower() for w in preceding_words[-neg_window:]]
            if any(w in negset for w in window):
                # This occurrence appears negated; skip it.
                continue
        return True
    return False


# --- Clamping ---

def clamp_score(value, default=50) -> int:
    """Clamp LLM-returned score to 0–100 int range."""
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return default


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp float to [lo, hi]."""
    return max(lo, min(hi, value))


# --- LLM response parsing ---

def extract_json_from_llm(content: str) -> dict | None:
    """Extract first JSON object from LLM response text. Returns None on failure."""
    match = re.search(r"\{[\s\S]*\}", content)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


# --- Range-to-label mapping ---

def range_label(value, thresholds, labels):
    """Map a numeric value to a label via bisect.
    len(labels) must equal len(thresholds) + 1.
    Example: range_label(85, [60,70,80,90], ["F","D","C","B","A"]) → "B"
    """
    return labels[bisect(thresholds, value)]


# --- Enums (str subclass so == "consultative" still works) ---

class Strategy(str, Enum):
    CONSULTATIVE = "consultative"
    TRANSACTIONAL = "transactional"
    INTENT = "intent"


class Stage(str, Enum):
    INTENT = "intent"
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    PITCH = "pitch"
    OBJECTION = "objection"
