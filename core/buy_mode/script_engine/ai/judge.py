"""Settle a close call: the AI picks one of the closest meanings, or says it is vague."""

import logging

from core.infra.logs import timed
from core.infra.utils import tokenize

VAGUE = "vague"
logger = logging.getLogger("script_engine.fallback")


def blanks(candidates, cfg):
    """The judge's own blanks in a prompt: the meanings to choose from and the allowed answers."""
    options = "\n".join(f"- {label}: e.g. {' / '.join(ex[:cfg["judge_examples"]])}" for label, ex in candidates.items())
    return {"options": options, "vague": VAGUE, "answers": ", ".join([*candidates, VAGUE])}


def pick(answer_text, candidates):
    """The one candidate the AI's answer names, or VAGUE (none, several, or it said vague)."""
    answer = tokenize(answer_text)
    found = [c for c in candidates if all(w in answer for w in tokenize(c))]
    return found[0] if len(found) == 1 and VAGUE not in answer else VAGUE


@timed
def judge(reply, candidates, llm, cfg):
    """candidates: {label: [examples]}. Any AI failure counts as vague, never blocks."""
    prompt = cfg["prompts"]["judge"].format(reply=reply, **blanks(candidates, cfg))
    try:
        return pick(llm(prompt, cfg["judge_tokens"]), candidates)
    except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
        logger.warning("judge failed, treating as vague: %s", exc)
        return VAGUE
