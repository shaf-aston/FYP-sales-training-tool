"""Layer 3 output checks for assistant replies."""

from dataclasses import dataclass, field

from .utils import Stage, contains_nonnegated_keyword


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


@dataclass
class Layer3CheckResult:
    """Output of Layer 3 checks."""

    content: str
    was_corrected: bool = False
    was_blocked: bool = False
    applied_rules: list[str] = field(default_factory=list)


def _normalize_stage_name(stage: str | Stage) -> str:
    stage_text = str(stage)
    if "." in stage_text:
        # Handles enum-style text like "Stage.LOGICAL".
        stage_text = stage_text.split(".", 1)[1]
    return stage_text.lower()


def _user_requested_pricing(user_message: str) -> bool:
    return contains_nonnegated_keyword(
        (user_message or "").lower(), DIRECT_PRICING_REQUEST_KEYWORDS
    )


def _contains_pricing_language(reply_text: str) -> bool:
    return contains_nonnegated_keyword((reply_text or "").lower(), PRICING_KEYWORDS)


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
    """Run Layer 3 checks and return corrected or blocked content.

    Checks are deterministic and stage-aware:
    1) Reject pricing leakage in logical and emotional stages.
    """
    stage_name = _normalize_stage_name(stage)
    text = (reply_text or "").strip()

    if not text:
        return Layer3CheckResult(
            content=_fallback_for_stage(stage_name),
            was_blocked=True,
            applied_rules=["empty_output_fallback"],
        )

    if stage_name in (Stage.LOGICAL.value, Stage.EMOTIONAL.value):
        if _contains_pricing_language(text) and not _user_requested_pricing(user_message):
            return Layer3CheckResult(
                content=_fallback_for_stage(stage_name),
                was_blocked=True,
                applied_rules=["blocked_pricing_in_discovery"],
            )

    return Layer3CheckResult(
        content=text,
        was_corrected=False,
        was_blocked=False,
        applied_rules=[],
    )
