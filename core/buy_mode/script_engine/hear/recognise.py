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
        self.question_answer_min_score = cfg["question_answer_min_score"]
        words = "|".join(rf"\b{re.escape(b)}\b" if b.isalpha() else re.escape(b) for b in cfg["clause_breaks"])
        self.breaks, self.clause_min_words = re.compile(words, re.I), cfg["clause_min_words"]

    def _parts(self, reply):
        """The reply, plus its clauses when it has two or more long enough to hear alone."""
        clauses = [c.strip() for c in self.breaks.split(reply) if len(c.split()) >= self.clause_min_words]
        return [reply] + clauses if len(clauses) > 1 else [reply]

    def match(self, reply, labels, by_clause=True, floors=None):
        """labels: {name: [example, ...]}. Score = best similarity per label, of the reply or (`by_clause`) any
        of its clauses. A meaning only the whole reply can have ("says nothing") is matched with by_clause=False.
        `floors`: {name: lowest score it counts at}; a name whose floor the best score misses is not a label
        or candidate."""
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
        return _floored(Match(label, top, tuple(n for n, _ in ranked[:self.k]), close), floors)

    def answer(self, reply, labels, unsure, floors=None):
        """As match, for the step's own answers: when the whole reply reaches no answer, a clear first clause
        is ("nope. my other half would go mental"): a question is answered first and explained after. A reply
        torn between two answers ("no, credit?") stays a close call: its lead never settles it. A lead nearer
        `unsure` (examples of not knowing) than any answer is none ("dunno, he's never..."). Never for
        interruptions, so "yeah but I need to think" still reads as an objection."""
        whole = self.match(reply, labels)
        found = _floored(whole, floors)
        if found.label or (whole.label and whole.close):  # torn between two answers: a floor never lets its lead settle it
            return found
        lead = self.breaks.split(reply, 1)[0].strip()
        if lead and lead != reply.strip():
            first = self.match(lead, labels, by_clause=False, floors=floors)
            if first.label and not first.close and first.score > self.match(lead, {"": unsure}, by_clause=False).score:
                return first
        return found

    def answer_score(self, reply, answers, asking):
        """How surely the reply is one of the step's `answers`; 0.0 when it is none. A question is one only
        when sure: "can we do option 2?" chooses, "what happens to the card?" asks about it."""
        found = self.match(reply, answers)
        if found.close and found.score >= self.threshold:
            return found.score  # torn between two answers ("no, credit?") is still answering
        bar = self.question_answer_min_score if asking else 0.0
        return found.score if found.label and found.score >= bar else 0.0

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
        as_answer = self.answer_score(reply, answers, asking) if answers else 0.0  # only a real answer competes
        bar = as_answer if answers else self.interrupt_threshold
        if any_reply:
            bar = max(bar, self.interrupt_threshold)
        if asking:
            bar = as_answer  # a question need beat only an answer it surely is
        bar = max(bar, floors.get(found.label, 0.0))
        return found.label if found.score > bar else None


def _floored(found, floors):
    """`found` with every name whose floor its best score misses taken out of the label and candidates."""
    floors = floors or {}
    candidates = tuple(n for n in found.candidates if found.score >= floors.get(n, 0.0))
    return Match(found.label if found.label in candidates else None, found.score, candidates, found.close)
