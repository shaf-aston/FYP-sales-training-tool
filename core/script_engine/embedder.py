"""Swap-seam for turning text into vectors. Recognition depends on this, never on an engine."""

from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one unit-length vector per text, all the same length."""
        ...
