"""Swap-seam for turning text into vectors. Recognition depends on this, never on an engine."""

from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one unit-length vector per text, all the same length."""
        ...

    def warm(self, texts: list[str]) -> None:
        """Pre-compute and remember vectors for the script's fixed examples."""
        ...


class FastEmbedEmbedder:
    """Local ONNX sentence embeddings. Only the script's examples are remembered, never replies."""

    def __init__(self, model, cache_dir, threads, batch_size):
        from fastembed import TextEmbedding  # heavy import, only when really used

        self._model = TextEmbedding(model_name=model, cache_dir=str(cache_dir), threads=threads)
        self._batch_size = batch_size
        self._seen = {}

    def _compute(self, texts):
        return [v.tolist() for v in self._model.embed(texts, batch_size=self._batch_size)]

    def warm(self, texts):
        new = [t for t in dict.fromkeys(texts) if t not in self._seen]
        if new:
            self._seen.update(zip(new, self._compute(new)))

    def embed(self, texts):
        fresh = [t for t in dict.fromkeys(texts) if t not in self._seen]
        got = dict(zip(fresh, self._compute(fresh))) if fresh else {}
        return [self._seen[t] if t in self._seen else got[t] for t in texts]


def make_embedder(cfg, root):
    """cfg = script/engine.yaml. Only place that knows which engine is behind the Embedder seam."""
    return FastEmbedEmbedder(cfg["embed_model"], root / cfg["embed_cache_dir"],
                             cfg["embed_threads"], cfg["embed_batch_size"])
