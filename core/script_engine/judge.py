"""Settle a close call: the AI picks one of the closest meanings, or says it is vague."""

import logging

from core.utils import tokenize

VAGUE = "vague"
logger = logging.getLogger("script_engine.fallback")


def judge(reply, candidates, llm, max_tokens):
    """candidates: {label: [examples]}. Any AI failure counts as vague, never blocks."""
    options = "\n".join(f"- {label}: e.g. {' / '.join(ex[:2])}" for label, ex in candidates.items())
    prompt = (
        "A prospect replied to a sales question. Which meaning fits best?\n"
        f"{options}\n- {VAGUE}: none of these clearly fits\n"
        f"Prospect reply: <reply>{reply}</reply>\nAnswer with exactly one of: {', '.join([*candidates, VAGUE])}."
    )
    try:
        answer = tokenize(llm(prompt, max_tokens))
    except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
        logger.warning("judge failed, treating as vague: %s", exc)
        return VAGUE
    found = [c for c in candidates if all(w in answer for w in tokenize(c))]
    return found[0] if len(found) == 1 and VAGUE not in answer else VAGUE
