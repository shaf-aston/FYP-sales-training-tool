"""Ask the AI for one sentence and keep it only if it passes every rule. The one retry loop."""

import logging

from core.script_engine.checks import check, clip

from ..logs import timed

logger = logging.getLogger("script_engine.fallback")


@timed
def checked_line(llm, prompt, tokens, ctx, cfg, label, clean=str.strip, retries=None):
    """Return the first AI answer that breaks no rule, or None.

    `clean` tidies the raw answer; returning None from it means the AI declined (stop now).
    """
    for _ in range(1 + (cfg["ai_retries"] if retries is None else retries)):
        try:
            text = clean(llm(prompt, tokens))
        except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
            logger.warning("%s: AI unavailable: %s", label, exc)
            return None
        if text is None:
            return None
        broken = check(text, ctx)
        if not broken:
            return text
        logger.warning("%s: AI line %r broke %s", label, clip(text, cfg["log_text_chars"]), broken)
    return None
