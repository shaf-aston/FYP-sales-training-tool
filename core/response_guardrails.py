"""LAYER 3: Response Validation - post-generation safety net.

Catches violations that bypass Layer 1 (FSM gating) and Layer 2 (prompt constraints):
- Pricing leakage in intent/logical/emotional stages
- Empty, degenerate, or oversized responses

Strips offending sentences first; uses a stage-specific fallback only when stripping
leaves fewer than MIN_RESPONSE_CHARS characters.
"""

import re
import random
from dataclasses import dataclass, field

from .utils import Stage, Strategy, contains_nonnegated_keyword
MIN_RESPONSE_CHARS = 40
MAX_RESPONSE_CHARS = 1500

# Stage-level guardrail keywords for pricing leakage during discovery.
PRICING_KEYWORDS = [
    "price",
    "pricing",
    "cost",
    "budget",
    "payment",
    "fee",
    "investment",
    "per month",
    "per year",
    "per week",
    "per annum",
    "annually",
    "monthly",
    "$",
]

# If the user asks for pricing directly, pricing mention is allowed.
DIRECT_PRICING_REQUEST_KEYWORDS = [
    "price",
    "pricing",
    "cost",
    "how much",
    "budget",
    "payment",
    "fee",
    "quote",
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_EXPLICIT_PRICE_REFERENCE = re.compile(
    r"(?:[$£€]\s*\d|\b\d+(?:[.,]\d+)?\s*(?:per\s+(?:month|week|year)|monthly|annually|annual|per\s+annum|fee|cost|price|pricing))",
    re.IGNORECASE,
)

_INTENT_FALLBACKS = [
    "What would you like help with first?",
    "What are you hoping to sort out today?",
    "What kind of outcome are you after?",
    "What brought you in today?",
]

_LOGICAL_FALLBACKS = [
    "What part of the current approach is not working?",
    "What feels most stuck right now?",
    "Where is the biggest gap showing up?",
]

_EMOTIONAL_FALLBACKS = [
    "What changed that made this feel urgent now?",
    "What would be different if this stayed the same?",
    "What is this costing you day to day?",
]

_EMOTIONAL_COI_PHRASES = [
    "staying the same",
    "stay the same",
    "what would happen if you don't change",
    "what would happen if nothing changed",
    "day to day",
    "continue down the current path",
    "costing you day to day",
]

_GENERIC_FALLBACKS = [
    "What should we focus on next?",
    "What would help most right now?",
]


@dataclass
class Layer3CheckResult:
    """Output of LAYER 3 (Response Validation) checks."""

    content: str
    was_corrected: bool = False
    was_blocked: bool = False
    applied_rules: list[str] = field(default_factory=list)

def _normalize_stage_name(stage: str | Stage) -> str:
    """Normalise a stage enum or string into a lowercase plain stage name."""
    stage_text = str(stage)
    if "." in stage_text:
        stage_text = stage_text.split(".", 1)[1]
    return stage_text.lower()


def _normalize_flow_type(flow_type: str | Stage | None) -> str:
    """Normalise a strategy enum or string into a lowercase plain strategy name."""
    if flow_type is None:
        return ""
    flow_text = str(flow_type)
    if "." in flow_text:
        flow_text = flow_text.split(".", 1)[1]
    return flow_text.lower()


def _user_requested_pricing(user_message: str) -> bool:
    """Return True when the user's message explicitly asks about price or terms."""
    return contains_nonnegated_keyword(
        (user_message or "").lower(), DIRECT_PRICING_REQUEST_KEYWORDS
    )


def _contains_pricing_language(reply_text: str) -> bool:
    """Return True when a reply contains pricing language or money terms."""
    return contains_nonnegated_keyword((reply_text or "").lower(), PRICING_KEYWORDS)


def _contains_consequence_of_inaction(text: str) -> bool:
    """Return True when the text talks about the cost of staying the same."""
    return contains_nonnegated_keyword((text or "").lower(), _EMOTIONAL_COI_PHRASES)


def _contains_explicit_price_reference(text: str) -> bool:
    """Return True when the text contains a concrete price reference."""
    return bool(_EXPLICIT_PRICE_REFERENCE.search(text or ""))


def _strip_pricing_sentences(text: str, stage_name: str = "") -> str:
    """Remove sentences containing pricing language; return remaining text."""
    sentences = _SENTENCE_SPLIT.split(text)
    clean = []
    for sentence in sentences:
        if not sentence:
            continue
        if (
            stage_name == Stage.EMOTIONAL.value
            and _contains_consequence_of_inaction(sentence)
            and not _contains_explicit_price_reference(sentence)
        ):
            clean.append(sentence)
            continue
        if not _contains_pricing_language(sentence):
            clean.append(sentence)
    return " ".join(clean).strip()


def _pick_varied_fallback(candidates: list[str], history: list[dict[str, str]] | None) -> str:
    """Pick a fallback that rotates naturally across turns."""
    if not candidates:
        return ""

    assistant_turns = 0
    if history:
        assistant_turns = sum(1 for msg in history if msg.get("role") == "assistant")

    return candidates[assistant_turns % len(candidates)]


def _fallback_for_stage(stage_name: str, history: list[dict[str, str]] | None = None) -> str:
    """Return deterministic fallback text for blocked replies."""
    if stage_name == Stage.LOGICAL.value:
        return _pick_varied_fallback(_LOGICAL_FALLBACKS, history)
    if stage_name == Stage.EMOTIONAL.value:
        return _pick_varied_fallback(_EMOTIONAL_FALLBACKS, history)
    if stage_name == Stage.INTENT.value:
        return _pick_varied_fallback(_INTENT_FALLBACKS, history)
    return _pick_varied_fallback(_GENERIC_FALLBACKS, history)


def apply_layer3_output_checks(
    reply_text: str,
    stage: str | Stage,
    user_message: str,
    flow_type: str | Stage | None = None,
    history: list[dict[str, str]] | None = None,
) -> Layer3CheckResult:
    """Run LAYER 3 (Response Validation) checks and return corrected or blocked content.

    Checks (in order):
    1) Degenerate output — empty, too short, or oversized.
    2) Pricing leakage in intent/logical/emotional stages, plus transactional pitch:
       a) Attempt sentence-level stripping first (was_corrected).
       b) Full fallback only when stripping leaves too little (was_blocked).
    """
    stage_name = _normalize_stage_name(stage)
    flow_name = _normalize_flow_type(flow_type)
    text = (reply_text or "").strip()

    if not text or len(text) < MIN_RESPONSE_CHARS:
        return Layer3CheckResult(
            content=_fallback_for_stage(stage_name, history),
            was_blocked=True,
            applied_rules=["empty_output_fallback"],
        )

    if len(text) > MAX_RESPONSE_CHARS:
        return Layer3CheckResult(
            content=_fallback_for_stage(stage_name, history),
            was_blocked=True,
            applied_rules=["oversized_output_fallback"],
        )

    if stage_name in (Stage.INTENT.value, Stage.LOGICAL.value, Stage.EMOTIONAL.value):
        if (
            stage_name == Stage.EMOTIONAL.value
            and _contains_consequence_of_inaction(text)
            and not _contains_explicit_price_reference(text)
        ):
            return Layer3CheckResult(content=text)
        if _contains_pricing_language(text) and not _user_requested_pricing(user_message):
            corrected = _strip_pricing_sentences(text, stage_name=stage_name)
            if len(corrected) >= MIN_RESPONSE_CHARS:
                return Layer3CheckResult(
                    content=corrected,
                    was_corrected=True,
                    applied_rules=["corrected_pricing_in_discovery"],
                )
            return Layer3CheckResult(
                content=_fallback_for_stage(stage_name, history),
                was_blocked=True,
                applied_rules=["blocked_pricing_in_discovery"],
            )

    if flow_name == Strategy.TRANSACTIONAL.value and stage_name == Stage.PITCH.value:
        if _contains_pricing_language(text):
            corrected = _strip_pricing_sentences(text)
            if len(corrected) >= MIN_RESPONSE_CHARS:
                return Layer3CheckResult(
                    content=corrected,
                    was_corrected=True,
                    applied_rules=["corrected_pricing_in_transactional_pitch"],
                )
            return Layer3CheckResult(
                content=_fallback_for_stage(stage_name, history),
                was_blocked=True,
                applied_rules=["blocked_pricing_in_transactional_pitch"],
            )

    return Layer3CheckResult(content=text)


