"""The one AI call that hears a reply against what the step is after: did they give it, a short "I heard
you" line if so, a fresh probe for it if not. Every line it writes is rule-checked; a failed line is dropped."""

import logging
import re
from dataclasses import dataclass

from core.script_engine.checks import check, clip

logger = logging.getLogger("script_engine.fallback")
KEY = re.compile(r"\b(ANSWERED|ACK|PROBE)\s*:", re.IGNORECASE)
NONE = ("", "none", "n/a", "-")


@dataclass(frozen=True)
class Heard:
    answered: bool
    ack: str = ""    # said before the next line when answered; "" when it failed a check
    probe: str = ""  # asked instead of the step's line when not answered; "" when it failed a check


def parse(raw):
    """The AI's three lines -> (answered, ack, probe), or None when ANSWERED is missing. Keys may share a
    line; the first of each key counts, so a later "ANSWERED:" inside a probe can't flip the verdict."""
    parts = KEY.split(raw)  # [junk, key, value, key, value, ...]
    found = {}
    for key, value in zip(parts[1::2], parts[2::2]):
        found.setdefault(key.upper(), value)
    verdict = found.get("ANSWERED", "").strip().lower()
    if not verdict.startswith(("yes", "no")):
        return None

    def tidy(text):
        text = text.strip().strip("`").strip().strip("\"'")
        return "" if text.lower() in NONE else text

    return verdict.startswith("yes"), tidy(found.get("ACK", "")), tidy(found.get("PROBE", ""))


def hear(llm, prompt, tokens, ack_ctx, probe_ctx, asked, cfg):
    """One checked listen. None when the AI fails or answers off-format (the caller falls back to rules).
    `asked`: every wording the step was asked in so far; a probe that repeats one is no probe."""
    try:
        raw = llm(prompt, tokens)
    except Exception as exc:  # noqa: BLE001 - any AI failure means fall back
        logger.warning("listen: AI unavailable: %s", exc)
        return None
    parsed = parse(raw)
    if parsed is None:
        logger.warning("listen: AI answered off-format %r", clip(raw, cfg["log_text_chars"]))
        return None
    answered, ack, probe = parsed
    if answered:
        broken = check(ack, ack_ctx) if ack else ["missing"]
        if broken:
            logger.warning("listen: ack %r broke %s", clip(ack, cfg["log_text_chars"]), broken)
        return Heard(True, "" if broken else ack)
    broken = check(probe, probe_ctx) if probe else ["missing"]
    if not broken and probe.strip().lower() in {a.strip().lower() for a in asked}:
        broken = ["same_words"]
    if broken:
        logger.warning("listen: probe %r broke %s", clip(probe, cfg["log_text_chars"]), broken)
    return Heard(False, probe="" if broken else probe)
