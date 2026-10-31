"""Small shared helpers: text matching, scores and ids."""

import json
import re
import secrets
from bisect import bisect
from functools import lru_cache

NEGATIONS = frozenset(
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


NEGATION_WINDOW = 3  # a negation this many words before a keyword cancels it


def contains_nonnegated_keyword(text: str, keywords) -> bool:
    """True when text contains a keyword (whole words) with no negation just before it."""
    keys = [keywords] if isinstance(keywords, str) else list(keywords or ())
    if not text or not keys:
        return False

    for match in _build_union_pattern_for_keywords(tuple(keys)).finditer(text):
        preceding_words = re.findall(r"\w+", text[: match.start()])
        if not any(w.lower() in NEGATIONS for w in preceding_words[-NEGATION_WINDOW:]):
            return True
    return False


def clamp_score(value, default=50) -> int:
    """Clamp a score to a 0-100 int"""
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


def tokenize(text: str) -> list[str]:
    """Split text into simple lowercase word tokens for rule-based scoring."""
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def is_question(text: str, cfg) -> bool:
    """A line asks something: it ends in "?" (unless it ends on a filler tag like "you get me?" or "right?"),
    or it opens like a question: a helper verb then a subject ("is this legit", "have you got proof"), a question
    word then a helper verb ("how do I know", "who are you"), or one of `question_starts`. Word lists from config."""
    spoken = " ".join(tokenize(text)) + " "
    tags = (" ".join(tokenize(tag)) for tag in cfg["filler_tags"])
    tagged = any(tag and (" " + spoken).endswith(" " + tag + " ") for tag in tags)
    return ((text or "").strip().endswith("?") and not tagged) or opens_question(text, cfg)


def opens_question(text: str, cfg) -> bool:
    """The words themselves ask, whatever the punctuation (see is_question). A question opening a later part
    counts too: "shut up and just tell me the price", "ok fine, how much is it"."""
    words = tokenize(text)
    first, second = (words + ["", ""])[:2]
    parts = (" ".join(tokenize(part)) + " " for part in re.split(r"[,.;:!]|\band\b", (text or "").lower()))
    return (
        (first in cfg["closed_question_starts"] and second in cfg["question_subjects"])
        or (first in cfg["question_words"] and second in cfg["closed_question_starts"])
        or any(part.startswith(phrase + " ") for part in parts for phrase in cfg["question_starts"])
    )


def merge_unique_items(*lists: list[str], max_items: int = 3) -> list[str]:
    """Merge list items in order, dropping duplicates (case-insensitive) and blanks.

    Stops after `max_items` so feedback lists stay short. Earlier lists win when
    deduplication trims the result.
    """
    seen = set()
    merged = []
    for items in lists:
        for item in items or []:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
            if len(merged) >= max_items:
                return merged
    return merged


def new_session_id() -> str:
    """A fresh id for a buy or sell session."""
    return secrets.token_hex(16)
