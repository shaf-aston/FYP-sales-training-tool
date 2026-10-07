"""Rule checks on any sentence the AI writes. Pure: text in, list of broken rules out."""

import re
from dataclasses import dataclass

from core.utils import tokenize

BLANK = re.compile(r"\{\w+(?:\|[^{}]*)?\}")  # {name} or {name|noun form|verb form}
CURRENCY = re.compile(r"[$£€]\s?\d")
FIGURE = re.compile(r"(\d[\d,.]*[a-z]*)(?:[ \t-]+([a-z]+))?")  # a number and the word it counts: "6-month"


def figures(text):
    """Each number in `text` with the word it counts ("6 month"), plural or not, so "6 calls" is not "6-month"."""
    return {f"{n} {(w or '').removesuffix('s')}".strip() for n, w in FIGURE.findall(text.lower())}


@dataclass(frozen=True)
class CheckContext:
    max_words: int
    questions: int                 # exact number of question marks the sentence must have
    price_ok: bool                 # the script has reached the price step
    price: str = ""                # the offer price, as written
    prospect_words: frozenset = None   # when set, every word must come from here or stop_words
    stop_words: frozenset = frozenset()
    known_figures: frozenset = None    # when set, every number (with the word it counts) must come from here
    banned: frozenset = frozenset()    # words the sentence must not use


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
    if ctx.known_figures is not None and figures(text) - ctx.known_figures:
        broken.append("new_number")
    if ctx.banned & set(tokenize(text)):
        broken.append("banned_word")
    if ctx.prospect_words is not None:
        foreign = set(tokenize(text)) - ctx.prospect_words - ctx.stop_words
        if foreign:
            broken.append("not_prospect_words")
    return broken
