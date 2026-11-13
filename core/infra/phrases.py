"""Does a line say a phrase? One rule for the whole app, so the buyer, the turn rating, the review and the score
can never disagree about what was said.

A phrase matches at the start of a word, whole words onward: "frustrat" finds "frustrated", "how" finds "how" but
never "show", "fit" never "benefit". A phrase that starts with a symbol ("$", "£") matches anywhere. Case and curly
apostrophes don't matter.
"""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=4096)
def _pattern(phrase: str) -> re.Pattern:
    p = phrase.lower().replace("’", "'")
    if not p[:1].isalnum():
        return re.compile(re.escape(p))
    return re.compile(rf"(?<![\w']){re.escape(p)}")


def _clean(text: str) -> str:
    return (text or "").lower().replace("’", "'")


def says(phrase: str, text: str) -> bool:
    """The text says the phrase (at the start of a word)."""
    return _pattern(phrase).search(_clean(text)) is not None


def says_any(phrases, text: str) -> bool:
    """The text says one of the phrases."""
    low = _clean(text)
    return any(_pattern(p).search(low) for p in phrases)


def says_word(words, text: str) -> bool:
    """The text has one of these as a whole word: "what" in "what's the problem?", never in "whatever"."""
    low = _clean(text)
    return any(re.search(rf"(?<![\w']){re.escape(w.lower())}(?!\w)", low) for w in words)
