"""Shared utilities — extracted to eliminate cross-module duplication."""
import json
import re
from bisect import bisect
from enum import Enum


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
