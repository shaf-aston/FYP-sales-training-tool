"""Turns text into vectors: the one local meaning model, shared by buy mode's hearing, Rep's words, SOP review and
the sell-mode buyer's lines. Callers only use embed() and warm(), so another engine can drop in here.
Settings: config/script/engine.yaml `embed_*` (they move to limits.yaml once that file is quiet)."""

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

from core.infra.env import ROOT_DIR
from core.infra.loader import load_yaml
from core.infra.logs import timed


class FastEmbedEmbedder:
    """Local ONNX sentence embeddings. Only the script's examples are remembered, never replies."""

    def __init__(self, model, cache_dir, threads, batch_size):
        from fastembed import TextEmbedding  # heavy import, only when really used

        self._model = TextEmbedding(model_name=model, cache_dir=str(cache_dir), threads=threads)
        self._batch_size = batch_size
        # the script's examples, kept on disk: a restart reads them back instead of embedding ~750 lines again
        # (most of the 36 s first-call wait on the small live VM, 25 Nov)
        self._file = Path(cache_dir) / f"seen-{model.replace('/', '_')}.npz"
        self._seen = self._load()

    def _load(self):
        try:
            with np.load(self._file) as f:
                return dict(zip(f["texts"].tolist(), f["vectors"].tolist()))
        except Exception:   # noqa: BLE001 - missing or broken: embed afresh
            return {}

    def _save(self):
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._file.with_suffix(".tmp.npz")
            np.savez(tmp, texts=np.array(list(self._seen)), vectors=np.array(list(self._seen.values()), dtype=np.float32))
            tmp.replace(self._file)
        except Exception:   # noqa: BLE001 - only a speed-up
            logging.getLogger(__name__).warning("embedder: could not save %s", self._file, exc_info=True)

    def _compute(self, texts):
        return [v.tolist() for v in self._model.embed(texts, batch_size=self._batch_size)]

    def warm(self, texts):
        new = [t for t in dict.fromkeys(texts) if t not in self._seen]
        if new:
            self._seen.update(zip(new, self._compute(new)))
            self._save()

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


@lru_cache(maxsize=1)
def shared_embedder():
    """One model per process: loading it is the slow part. Look it up through this module
    (`embedder.shared_embedder()`), so tests can swap it."""
    return make_embedder(load_yaml("script/engine.yaml"), ROOT_DIR)
