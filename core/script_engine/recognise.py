"""Match a prospect reply to the closest labelled meaning. Pure given an embedder."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    label: str | None   # best label, or None when below threshold
    score: float        # best similarity found
    candidates: tuple   # top-k label names, best first
    close: bool         # too near to call: hand to the judge


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def recognise(reply, labels, embedder, threshold, margin, k):
    """labels: {name: [example, ...]}. Score = best example similarity per label."""
    names, examples = [], []
    for name, items in labels.items():
        names += [name] * len(items)
        examples += items
    vectors = embedder.embed([reply] + examples)
    best = {}
    for name, vec in zip(names, vectors[1:]):
        best[name] = max(best.get(name, -1.0), _dot(vectors[0], vec))
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return Match(None, 0.0, (), False)
    top_name, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else -1.0
    near_miss = threshold - 0.1 <= top < threshold
    close = (top - second < margin and top >= threshold - 0.1) or near_miss
    label = top_name if top >= threshold else None
    return Match(label, top, tuple(n for n, _ in ranked[:k]), close)
