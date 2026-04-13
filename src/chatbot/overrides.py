"""Prompt overrides for direct requests, soft positives, and over-validation"""

from .analysis import is_repetitive_validation
from .loader import get_override_template, loadSIGNALS
from .utils import contains_nonnegated_keyword

SIGNALS = loadSIGNALS()


def check_override_condition(base_prompt, user_message, stage, history, preferences):
    """Return override prompt if condition met, else None."""
    # direct info request — respond with data immediately
    direct_info_requests = SIGNALS.get("direct_info_requests", [])
    if contains_nonnegated_keyword(user_message, direct_info_requests):
        return get_override_template(
            "direct_info_request", base=base_prompt, preferences=preferences or "not yet specified"
        )

    # soft positive at pitch — assumptive close
    soft_positiveSIGNALS = SIGNALS.get("soft_positive", [])
    if contains_nonnegated_keyword(user_message, soft_positiveSIGNALS) and stage == "pitch":
        return get_override_template(
            "soft_positive_at_pitch",
            base=base_prompt,
            user_message=user_message,
            preferences=preferences or "price, reliability, features",
        )

    # too much validation — force substance
    if is_repetitive_validation(history):
        return get_override_template(
            "excessive_validation", base=base_prompt, preferences=preferences or "Not yet extracted"
        )

    return None
