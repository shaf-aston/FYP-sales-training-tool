"""Settle a close call: the AI picks one of the closest meanings, or says it is vague."""

import logging

from core.script_engine.checks import words

VAGUE = "vague"
logger = logging.getLogger("script_engine.fallback")


def judge(reply, candidates, llm):
    """candidates: {label: [examples]}. Any AI failure counts as vague, never blocks."""
    options = "\n".join(f"- {label}: e.g. {' / '.join(ex[:2])}" for label, ex in candidates.items())
    prompt = (
        "A prospect replied to a sales question. Which meaning fits best?\n"
        f"{options}\n- {VAGUE}: none of these clearly fits\n"
        f"Reply: {reply}\nAnswer with exactly one of: {', '.join([*candidates, VAGUE])}."
    )
    try:
        answer = words(llm(prompt, 10))
    except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
        logger.warning("judge failed, treating as vague: %s", exc)
        return VAGUE
    return next((label for label in candidates if label.lower() in answer), VAGUE)
