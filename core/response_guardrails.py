"""LAYER 3: Response Validation - post-generation safety net.

Catches violations that bypass Layer 1 (FSM gating) and Layer 2 (prompt constraints):
- Prices the product data does not contain (invented), at any stage
- Price talk in discovery stages, or transactional pitch, before the buyer asks
- Empty, degenerate, or oversized responses

Strips offending sentences first; uses a fallback line from config/guardrails.yaml only
when stripping leaves fewer than MIN_RESPONSE_CHARS characters.
"""

import logging
import re
from dataclasses import dataclass, field

from .constants import MIN_RESPONSE_CHARS, MAX_RESPONSE_CHARS
from .loader import load_signals, load_yaml
from .utils import Stage, Strategy, contains_nonnegated_keyword

logger = logging.getLogger(__name__)

_CONFIG = load_yaml("guardrails.yaml")
_BILLING_TERMS = _CONFIG["billing_terms"]
_NO_PRICE_STAGES = set(_CONFIG["no_price_stages"])
_FALLBACKS = _CONFIG["fallback_lines"]
_PRICE_REQUESTS = load_signals()["direct_info_requests"]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
# A money figure: "$99", "£2,400", "99 dollars", "49 pounds".
_MONEY = re.compile(
    r"[$£€]\s*(\d[\d,]*(?:\.\d+)?)|\b(\d[\d,]*(?:\.\d+)?)\s*(?:dollars|pounds|euros|usd|gbp|eur)\b",
    re.IGNORECASE,
)


@dataclass
class Layer3CheckResult:
    """Output of LAYER 3 (Response Validation) checks."""

    content: str
    was_corrected: bool = False
    was_blocked: bool = False
    applied_rules: list[str] = field(default_factory=list)


def _plain_name(value) -> str:
    """Lowercase plain name for a Stage/Strategy enum or string ('Stage.PITCH' -> 'pitch')."""
    text = str(value or "")
    return text.split(".", 1)[-1].lower()


def _money_amounts(text: str) -> set[str]:
    """Every money figure in the text, commas removed."""
    return {(a or b).replace(",", "") for a, b in _MONEY.findall(text or "")}


def _talks_price(sentence: str) -> bool:
    """True when a sentence quotes a money figure or states billing terms."""
    return bool(_MONEY.search(sentence)) or contains_nonnegated_keyword(
        sentence.lower(), _BILLING_TERMS
    )


def _strip_prompt_markers(text: str) -> str:
    """Remove BEGIN/END CUSTOM PRODUCT DATA blocks; they are internal prompt context."""
    text = re.sub(
        r"---\s*BEGIN\s+CUSTOM\s+PRODUCT\s+DATA\s*---.*?---\s*END\s+CUSTOM\s+PRODUCT\s+DATA\s*---",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"---\s*(BEGIN|END)\s+CUSTOM\s+PRODUCT\s+DATA\s*---", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _no_dashes(text: str) -> str:
    """House style: no em or en dashes in replies; a spaced dash becomes a comma."""
    text = re.sub(r"\s*[20142013]\s*(?=\w)", ", ", text)
    return re.sub(r"\s*[20142013]\s*", " ", text).strip()


def _keep_sentences(text: str, drop) -> str:
    """Join the sentences for which drop(sentence) is False."""
    return " ".join(s for s in _SENTENCE_SPLIT.split(text) if s and not drop(s)).strip()


def _fallback(stage_name: str, price_asked: bool, history) -> str:
    """Pick a fallback line in turn order, so a replayed chat gets the same line."""
    if price_asked:
        lines = _FALLBACKS["price_question"]
    else:
        lines = _FALLBACKS.get(stage_name) or _FALLBACKS["default"]
    turn = len(history or []) // 2
    return lines[turn % len(lines)]


def apply_layer3_output_checks(
    reply_text: str,
    stage,
    user_message: str,
    flow_type=None,
    history: list[dict[str, str]] | None = None,
    product_context: str | None = None,
) -> Layer3CheckResult:
    """Run LAYER 3 checks and return corrected or blocked content.

    Checks (in order):
    0) Strip internal prompt markers.
    1) Degenerate output: empty, too short, or oversized.
    2) Invented prices: a money figure not found in product_context (skipped when None).
    3) Early price talk: in no_price_stages and transactional pitch, unless the buyer asked.
    Each price check strips sentences first and falls back only when too little is left.
    """
    stage_name = _plain_name(stage)
    flow_name = _plain_name(flow_type)
    price_asked = contains_nonnegated_keyword((user_message or "").lower(), _PRICE_REQUESTS)
    text = _no_dashes(reply_text or "")

    if "CUSTOM PRODUCT DATA" in text:
        text = _strip_prompt_markers(text)

    if len(text) < MIN_RESPONSE_CHARS:
        return Layer3CheckResult(
            content=_fallback(stage_name, price_asked, history),
            was_blocked=True,
            applied_rules=["empty_output_fallback"],
        )

    if len(text) > MAX_RESPONSE_CHARS:
        truncated = text[:MAX_RESPONSE_CHARS]
        boundary = max(truncated.rfind(". "), truncated.rfind("? "), truncated.rfind("! "))
        if boundary > 0:
            truncated = truncated[: boundary + 1]
        return Layer3CheckResult(
            content=truncated.strip(),
            was_corrected=True,
            applied_rules=["oversized_output_truncated"],
        )

    rules = []
    if product_context is not None:
        known = _money_amounts(product_context)
        if _money_amounts(text) - known:
            text = _keep_sentences(text, lambda s: bool(_money_amounts(s) - known))
            rules.append("invented_price")

    early = stage_name in _NO_PRICE_STAGES or (
        flow_name == Strategy.TRANSACTIONAL.value and stage_name == Stage.PITCH.value
    )
    if early and not price_asked and any(_talks_price(s) for s in _SENTENCE_SPLIT.split(text)):
        text = _keep_sentences(text, _talks_price)
        rules.append("early_price")

    if not rules:
        return Layer3CheckResult(content=text)
    logger.debug("layer3: %s in %s stage", rules, stage_name)
    if len(text) >= MIN_RESPONSE_CHARS:
        return Layer3CheckResult(content=text, was_corrected=True, applied_rules=rules)
    return Layer3CheckResult(
        content=_fallback(stage_name, price_asked, history),
        was_blocked=True,
        applied_rules=rules,
    )


_BUYER = _CONFIG["buyer"]
_BUYER_COMMITS = load_signals()["commitment"]


def check_buyer_reply(reply_text: str, turn: int) -> Layer3CheckResult:
    """Run LAYER 3 checks on an AI-buyer reply (prospect mode).

    The session rules own the outcome, so the buyer may not agree to buy on its own.
    Drops sentences that commit or step out of character, then caps the length.
    Falls back to a config line, picked by turn, when too little is left.
    """
    text = _no_dashes(reply_text or "")
    rules = []

    def bad(sentence: str) -> bool:
        lowered = sentence.lower()
        if contains_nonnegated_keyword(lowered, _BUYER["out_of_character"]):
            rules.append("buyer_out_of_character")
            return True
        if contains_nonnegated_keyword(lowered, _BUYER_COMMITS):
            rules.append("buyer_committed")
            return True
        return False

    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s and not bad(s)]
    if len(sentences) > _BUYER["max_sentences"]:
        sentences = sentences[: _BUYER["max_sentences"]]
        rules.append("buyer_too_long")
    text = " ".join(sentences).strip()

    if not text or (rules and len(text) < MIN_RESPONSE_CHARS // 2):
        lines = _BUYER["fallback_lines"]
        return Layer3CheckResult(
            content=lines[turn % len(lines)],
            was_blocked=True,
            applied_rules=rules or ["empty_output_fallback"],
        )
    rules = list(dict.fromkeys(rules))
    return Layer3CheckResult(content=text, was_corrected=bool(rules), applied_rules=rules)
