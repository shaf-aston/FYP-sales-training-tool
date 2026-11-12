"""How alike two lists of texts are in meaning: cosine similarity of their embeddings, through the `embed` the caller
gives (texts -> vectors), and the one-to-one pairing of the closest. Plain Python: the lists are a few hundred lines
at most (an SOP, a call, a script). Used by SOP review and by the rep's own words in buy mode."""

from __future__ import annotations

import math
from collections.abc import Callable

Embed = Callable[[list[str]], list[list[float]]]


def _unit(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


def similarity(rows: list[str], cols: list[str], embed: Embed) -> list[list[float]]:
    """similarity[i][j] = how alike rows[i] and cols[j] are, -1..1."""
    if not rows or not cols:
        return [[] for _ in rows]
    vectors = [_unit(v) for v in embed(list(rows) + list(cols))]
    a, b = vectors[: len(rows)], vectors[len(rows):]
    return [[sum(x * y for x, y in zip(u, v)) for v in b] for u in a]


def best_pairs(scores: list[list[float]], bar: float) -> dict[int, int]:
    """Row -> column, one to one: the strongest pairs at or above `bar` first, each row and each column used at most
    once, so one line never counts for two things."""
    pairs = sorted(((v, i, j) for i, row in enumerate(scores) for j, v in enumerate(row) if v >= bar), reverse=True)
    match: dict[int, int] = {}
    used: set[int] = set()
    for _, i, j in pairs:
        if i not in match and j not in used:
            match[i] = j
            used.add(j)
    return match
