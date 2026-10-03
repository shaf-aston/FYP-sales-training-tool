"""Swap-seam for turning text into vectors. Recognition depends on this, never on an engine."""

from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one unit-length vector per text, all the same length."""
        ...


class FastEmbedEmbedder:
    """Local ONNX sentence embeddings. Repeated texts (the script's examples) are cached."""

    def __init__(self, model, cache_dir):
        from fastembed import TextEmbedding  # heavy import, only when really used

        self._model = TextEmbedding(model_name=model, cache_dir=str(cache_dir))
        self._seen = {}

    def embed(self, texts):
        new = [t for t in dict.fromkeys(texts) if t not in self._seen]
        if new:
            self._seen.update(zip(new, (v.tolist() for v in self._model.embed(new))))
        return [self._seen[t] for t in texts]


def make_embedder(cfg, root):
    """cfg = selling.yaml. Only place that knows which engine is behind the Embedder seam."""
    return FastEmbedEmbedder(cfg["embed_model"], root / cfg["embed_cache_dir"])
