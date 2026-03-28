"""Logic for detecting and applying early-return override prompts (direct requests, soft positives)."""

from .loader import load_signals, get_override_template
from .analysis import text_contains_any_keyword, is_repetitive_validation

_SIGNALS = load_signals()


def check_override_condition(base_prompt, user_message, stage, history, preferences):
    """Check for early-return override conditions.

    Returns override prompt if condition met, else None. Checks in priority order:
    1. Direct information request → provide options immediately
    2. Soft positive at pitch → assumptive close
    3. Excessive validation → force substance
    """
    # Direct information request — override everything, respond with data
    direct_info_requests = _SIGNALS.get("direct_info_requests", [])
    if text_contains_any_keyword(user_message, direct_info_requests):
        return get_override_template(
            "direct_info_request",
            base=base_prompt,
            preferences=preferences or "not yet specified"
        )

    # Soft positive at pitch stage — assumptive close
    soft_positive_signals = _SIGNALS.get("soft_positive", [])
    if text_contains_any_keyword(user_message, soft_positive_signals) and stage == "pitch":
        return get_override_template(
            "soft_positive_at_pitch",
            base=base_prompt,
            user_message=user_message,
            preferences=preferences or "price, reliability, features"
        )

    # Excessive validation — force substance
    if is_repetitive_validation(history):
        return get_override_template(
            "excessive_validation",
            base=base_prompt,
            preferences=preferences or "Not yet extracted"
        )

    return None
