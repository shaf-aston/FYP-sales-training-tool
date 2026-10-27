"""Turns text into vectors. Recognition only calls embed() and warm(), so another engine can drop in here."""

from core.infra.logs import timed


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

    @timed
    def embed(self, texts):
        fresh = [t for t in dict.fromkeys(texts) if t not in self._seen]
        got = dict(zip(fresh, self._compute(fresh))) if fresh else {}
        return [self._seen[t] if t in self._seen else got[t] for t in texts]


@timed
def make_embedder(cfg, root):
    """cfg = script/engine.yaml. The only place that picks the engine."""
    return FastEmbedEmbedder(cfg["embed_model"], root / cfg["embed_cache_dir"],
                             cfg["embed_threads"], cfg["embed_batch_size"])
