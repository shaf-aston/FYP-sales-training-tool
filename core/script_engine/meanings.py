"""The meaning bank (config/script/meanings.yaml): a prewritten line for what an answer means beyond its
words ("my mum's relying on me": family duty), picked by the local matcher. No AI, and no quoting them."""

from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType

from core.loader import CONFIG_DIR
from core.script_engine.config import plain_words
from core.script_engine.method import _one_stress, _read, _score
from core.utils import tokenize


@dataclass(frozen=True)
class Meaning:
    name: str
    examples: tuple
    lines: tuple        # said in turn, each once a call; none of them asks


@dataclass(frozen=True)
class Meanings:
    items: MappingProxyType  # read-only: one bank is shared by every call (load_meanings is cached)
    min_score: float    # an answer means one only when it matches this well
    min_words: int = 2  # and says this many words that carry meaning: "debt" or "for my mum" means none


def parse_meanings(data):
    items = {}
    for k, v in (data.get("meanings") or {}).items():
        if not v.get("examples") or not v.get("lines"):
            raise ValueError(f"meaning {k}: needs examples and lines")
        for line in v["lines"]:
            if "?" in line or "{" in line:
                raise ValueError(f"meaning {k}: a line neither asks nor has blanks (the step's question follows): {line!r}")
            _one_stress(f"meaning {k}", line)
        items[k] = Meaning(k, tuple(v["examples"]), tuple(v["lines"]))
    min_words = data.get("min_words", Meanings.min_words)
    if not isinstance(min_words, int) or isinstance(min_words, bool) or min_words < 1:
        raise ValueError("meanings: min_words must be a whole number of at least 1")
    return Meanings(MappingProxyType(items), _score("meanings", data.get("min_score")), min_words)


@lru_cache(maxsize=1)
def load_meanings(name="meanings", directory=CONFIG_DIR / "script"):
    return parse_meanings(_read(directory, name))


class MeaningBank:
    """Picks the line for what a reply means."""

    def __init__(self, cfg, meanings, listener):
        self._meanings, self._listener, self._plain = meanings, listener, plain_words(cfg)
        self._labels = {k: list(m.examples) for k, m in meanings.items.items()}

    def examples(self):
        return [e for items in self._labels.values() for e in items]

    def line(self, reply, said):
        """The next line not in `said` for what the reply means; "" when it means none (or all were said)."""
        if not self._labels or len(set(tokenize(reply)) - self._plain) < self._meanings.min_words:
            return ""  # too few words to mean anything this deep: "debt", "for my mum"
        found = self._listener.match(reply, self._labels)
        if found.score < self._meanings.min_score:
            return ""
        return next((line for line in self._meanings.items[found.candidates[0]].lines if line not in said), "")
