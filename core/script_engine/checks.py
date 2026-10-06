"""Rule checks on any sentence the AI writes. Pure: text in, list of broken rules out."""

import re
from dataclasses import dataclass

from core.utils import tokenize

BLANK = re.compile(r"\{\w+\}")
CURRENCY = re.compile(r"[$£€]\s?\d")
LINK = re.compile(r"https?://|www\.|@|\.(com|net|org|io)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CheckContext:
    max_words: int
    questions: int                 # exact number of question marks the sentence must have
    price_ok: bool                 # the script has reached the price step
    price: str = ""                # the offer price, as written
    prospect_words: frozenset = None   # when set, every word must come from here or stop_words
    stop_words: frozenset = frozenset()
    banned_words: frozenset = frozenset()


def clip(text, limit):
    """Cut prospect text before it reaches a log."""
    return text if len(text) <= limit else text[:limit] + "..."


def check(text, ctx):
    """Return the names of every rule `text` breaks (empty = clean)."""
    low = text.lower()
    broken = []
    if text.count("?") != ctx.questions:
        broken.append("question_count")
    if re.search(r"\bbut\b", low):
        broken.append("says_but")
    if "you said" in low:
        broken.append("says_you_said")
    if "any questions" in low:
        broken.append("any_questions")
    if not ctx.price_ok and (CURRENCY.search(text) or (ctx.price and ctx.price in text)):
        broken.append("early_price")
    if BLANK.search(text):
        broken.append("unfilled_blank")
    if not text.strip() or len(tokenize(text)) > ctx.max_words:
        broken.append("length")
    if LINK.search(text):
        broken.append("link")
    if ctx.banned_words & set(tokenize(text)):
        broken.append("banned_word")
    if ctx.prospect_words is not None:
        foreign = set(tokenize(text)) - ctx.prospect_words - ctx.stop_words
        if foreign:
            broken.append("not_prospect_words")
    return broken
