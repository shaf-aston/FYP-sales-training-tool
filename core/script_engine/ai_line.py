"""Ask the AI for one sentence and keep it only if it passes every rule. The one retry loop."""

import logging

from core.script_engine.checks import check, clip

logger = logging.getLogger("script_engine.fallback")


def checked_line(llm, prompt, tokens, ctx, cfg, label, clean=str.strip, extra_rules=None):
    """Return the first AI answer that breaks no rule, or None.

    `clean` tidies the raw answer; returning None from it means the AI declined (stop now).
    `extra_rules(text)` adds caller-specific broken-rule names to the shared `check`.
    """
    for _ in range(1 + cfg["ai_retries"]):
        try:
            text = clean(llm(prompt, tokens))
        except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
            logger.warning("%s: AI unavailable: %s", label, exc)
            return None
        if text is None:
            return None
        broken = check(text, ctx) + (extra_rules(text) if extra_rules else [])
        if not broken:
            return text
        logger.warning("%s: AI line %r broke %s", label, clip(text, cfg["log_text_chars"]), broken)
    return None
