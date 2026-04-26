"""LAYER 3: Response Validation - post-generation safety net.

Catches violations that bypass Layer 1 (FSM gating) and Layer 2 (prompt constraints):
- Pricing leakage in intent/logical/emotional stages
- Empty, degenerate, or oversized responses

Strips offending sentences first; uses a stage-specific fallback only when stripping
leaves fewer than MIN_RESPONSE_CHARS characters.
"""

import re
from dataclasses import dataclass, field

from .utils import Stage, contains_nonnegated_keyword
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


@dataclass
class Layer3CheckResult:
    """Output of LAYER 3 (Response Validation) checks."""

    content: str
    was_corrected: bool = False
    was_blocked: bool = False
    applied_rules: list[str] = field(default_factory=list)

def _normalize_stage_name(stage: str | Stage) -> str:
    stage_text = str(stage)
    if "." in stage_text:
        stage_text = stage_text.split(".", 1)[1]
    return stage_text.lower()


def _user_requested_pricing(user_message: str) -> bool:
    return contains_nonnegated_keyword(
        (user_message or "").lower(), DIRECT_PRICING_REQUEST_KEYWORDS
    )


def _contains_pricing_language(reply_text: str) -> bool:
    return contains_nonnegated_keyword((reply_text or "").lower(), PRICING_KEYWORDS)


def _strip_pricing_sentences(text: str) -> str:
    """Remove sentences containing pricing language; return remaining text."""
    sentences = _SENTENCE_SPLIT.split(text)
    clean = [s for s in sentences if s and not _contains_pricing_language(s)]
    return " ".join(clean).strip()


def _fallback_for_stage(stage_name: str) -> str:
    """Return deterministic fallback text for blocked replies."""
    if stage_name == Stage.LOGICAL.value:
        return (
            "Let us stay with your current process for a moment and pinpoint what is "
            "not working most consistently."
        )
    if stage_name == Stage.EMOTIONAL.value:
        return (
            "Let us stay on impact for a moment and clarify what this problem is "
            "costing you day to day."
        )
    if stage_name == Stage.INTENT.value:
        return "Let us start with what you are trying to achieve so I can guide you clearly."
    return "Let us continue one step at a time and keep this focused on your goal."


def apply_layer3_output_checks(
    reply_text: str,
    stage: str | Stage,
    user_message: str,
) -> Layer3CheckResult:
    """Run LAYER 3 (Response Validation) checks and return corrected or blocked content.

    Checks (in order):
    1) Degenerate output — empty, too short, or oversized.
    2) Pricing leakage in intent/logical/emotional stages:
       a) Attempt sentence-level stripping first (was_corrected).
       b) Full fallback only when stripping leaves too little (was_blocked).
    """
    stage_name = _normalize_stage_name(stage)
    text = (reply_text or "").strip()

    if not text or len(text) < MIN_RESPONSE_CHARS:
        return Layer3CheckResult(
            content=_fallback_for_stage(stage_name),
            was_blocked=True,
            applied_rules=["empty_output_fallback"],
        )

    if len(text) > MAX_RESPONSE_CHARS:
        return Layer3CheckResult(
            content=_fallback_for_stage(stage_name),
            was_blocked=True,
            applied_rules=["oversized_output_fallback"],
        )

    if stage_name in (Stage.INTENT.value, Stage.LOGICAL.value, Stage.EMOTIONAL.value):
        if _contains_pricing_language(text) and not _user_requested_pricing(user_message):
            corrected = _strip_pricing_sentences(text)
            if len(corrected) >= MIN_RESPONSE_CHARS:
                return Layer3CheckResult(
                    content=corrected,
                    was_corrected=True,
                    applied_rules=["corrected_pricing_in_discovery"],
                )
            return Layer3CheckResult(
                content=_fallback_for_stage(stage_name),
                was_blocked=True,
                applied_rules=["blocked_pricing_in_discovery"],
            )

    return Layer3CheckResult(content=text)


