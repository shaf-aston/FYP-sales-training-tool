"""Checks on AI-buyer replies (prospect mode) before the user sees them.

The session rules own the outcome, so the buyer may not agree to buy on its own: sentences
that commit are dropped, and a config line is used only when nothing is left.
"""

import re
from dataclasses import dataclass, field

from .loader import load_yaml
from .utils import contains_nonnegated_keyword

_BUYER = load_yaml("guardrails.yaml")["buyer"]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class Layer3CheckResult:
    """A checked reply and what was changed."""

    content: str
    was_corrected: bool = False
    was_blocked: bool = False
    applied_rules: list[str] = field(default_factory=list)


_DASH = f"[{chr(0x2014)}{chr(0x2013)}]"  # em and en dash


def _no_dashes(text: str) -> str:
    """House style: no em or en dashes in replies; a spaced dash becomes a comma."""
    text = re.sub(r"\s*" + _DASH + r"\s*(?=\w)", ", ", text)
    return re.sub(r"\s*" + _DASH + r"\s*", " ", text).strip()


def _keep_sentences(text: str, drop) -> str:
    """Join the sentences for which drop(sentence) is False."""
    return " ".join(s for s in _SENTENCE_SPLIT.split(text) if s and not drop(s)).strip()


def check_buyer_reply(reply_text: str, turn: int) -> Layer3CheckResult:
    """Drop sentences where the buyer commits to buying; fall back by turn when nothing is left."""
    text = _no_dashes(reply_text or "")
    rules = []

    def bad(sentence: str) -> bool:
        if contains_nonnegated_keyword(sentence.lower(), _BUYER["commitment"]):
            rules.append("buyer_committed")
            return True
        return False

    text = _keep_sentences(text, bad)

    if not text:
        lines = _BUYER["fallback_lines"]
        return Layer3CheckResult(
            content=lines[turn % len(lines)],
            was_blocked=True,
            applied_rules=rules or ["empty_output_fallback"],
        )
    rules = list(dict.fromkeys(rules))
    return Layer3CheckResult(content=text, was_corrected=bool(rules), applied_rules=rules)
