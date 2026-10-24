"""Match a prospect reply to the closest labelled meaning. Pure given an embedder."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    label: str | None   # best label, or None when below threshold
    score: float        # best similarity found
    candidates: tuple   # top-k label names, best first
    close: bool         # too near to call: hand to the judge


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class Listener:
    """Hears a reply against labelled meanings, with the thresholds from `cfg`. Built once per seller."""

    def __init__(self, cfg, embedder):
        self.embedder = embedder
        self.threshold, self.margin, self.k = cfg["threshold"], cfg["margin"], cfg["close_call_k"]
        self.near_miss, self.interrupt_threshold = cfg["near_miss"], cfg["interrupt_threshold"]
        words = "|".join(rf"\b{re.escape(b)}\b" if b.isalpha() else re.escape(b) for b in cfg["clause_breaks"])
        self.breaks, self.clause_min_words = re.compile(words, re.I), cfg["clause_min_words"]

    def _parts(self, reply):
        """The reply, plus its clauses when it has two or more long enough to hear alone."""
        clauses = [c.strip() for c in self.breaks.split(reply) if len(c.split()) >= self.clause_min_words]
        return [reply] + clauses if len(clauses) > 1 else [reply]

    def match(self, reply, labels, by_clause=True):
        """labels: {name: [example, ...]}. Score = best similarity per label, of the reply or (`by_clause`) any
        of its clauses. A meaning only the whole reply can have ("says nothing") is matched with by_clause=False."""
        names, examples = [], []
        for name, items in labels.items():
            names += [name] * len(items)
            examples += items
        parts = self._parts(reply) if by_clause else [reply]
        vectors = self.embedder.embed(parts + examples)
        heard, best = vectors[:len(parts)], {}
        for name, vec in zip(names, vectors[len(parts):]):
            best[name] = max(best.get(name, -1.0), *(_dot(h, vec) for h in heard))
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        if not ranked:
            return Match(None, 0.0, (), False)
        top_name, top = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else -1.0
        in_band = self.threshold - self.near_miss <= top < self.threshold
        close = (top - second < self.margin and top >= self.threshold - self.near_miss) or in_band
        label = top_name if top >= self.threshold else None
        return Match(label, top, tuple(n for n, _ in ranked[:self.k]), close)

    def interruption(self, reply, labels, answers, any_reply, asking, floors):
        """The label in `labels` that clearly beats reading the reply as one of the step's own `answers`,
        else None. `any_reply`: the step takes any reply as its answer, so only a sure match interrupts.
        `asking`: the reply is a question. `floors`: {label: lowest score it counts at}. A "fact:" label always wins: a product question
        is never an answer."""
        found = self.match(reply, labels)
        if not found.label or found.close:
            return None
        if found.label.startswith("fact:"):
            return found.label
        bar = self.interrupt_threshold
        if answers:
            as_answer = self.match(reply, answers)
            bar = as_answer.score if as_answer.label else 0.0  # only a real answer competes
        if any_reply:
            bar = max(bar, self.interrupt_threshold)
        if asking:
            bar = 0.0  # a question is never an answer, so it need not beat one
        bar = max(bar, floors.get(found.label, 0.0))
        return found.label if found.score > bar else None
