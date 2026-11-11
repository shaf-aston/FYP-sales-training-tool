"""How alike two lists of texts are in meaning: cosine similarity of their embeddings, through the `embed` the caller
gives (texts -> vectors). Plain Python: an SOP and a call are a few hundred lines at most."""

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
