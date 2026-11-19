"""A second layer under the turn rules: flags what they miss when it is said in other words.

The rules (turn_rating.py) catch "act now" but not "you'd be kicking yourself if you let this slide"; this catches
that kind of thing: pushy, dismissive, leading, ignored (the buyer said something that mattered and the reply
moved on), feature_dump. A small model trained on hand-written examples (scripts/blemish/) reads the shared
embedder's vectors of the buyer's line and the seller's reply. It only adds flags, never changes a rating, and
says nothing where the rules already did (a turn already marked pushy by them is not flagged pushy again).

Off when the model file is missing, the blemish is switched off in it (it did not hold up on the test set), or the
embedder is unavailable: the review is the same as before, without the flags.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

from core.infra import embedder as meaning_model
from core.infra.env import ROOT_DIR
from core.infra.loader import load_yaml

logger = logging.getLogger(__name__)


def _cfg() -> dict:
    return load_yaml("call_stages.yaml")["blemish"]


@lru_cache(maxsize=1)
def _model():
    path = ROOT_DIR / _cfg()["model"]
    if not path.exists():
        return None
    data = np.load(path)
    return {k: data[k] for k in data.files}


def notice(turns: list[dict]) -> dict[int, list[dict]]:
    """{turn number: [{label, reason, confidence}]} for the turns the model flags. `turns`: build_review's."""
    cfg, model = _cfg(), _model()
    if not cfg.get("enabled", True) or model is None or not model["enabled"].any() or not turns:
        return {}
    try:
        texts = sorted({t.get(k) or "" for t in turns for k in ("seller", "buyer_before")})
        vec = dict(zip(texts, (np.asarray(v, dtype=np.float32) for v in meaning_model.shared_embedder().embed(texts))))
        x = np.stack([np.concatenate([vec[t["seller"] or ""], vec[t.get("buyer_before") or ""],
                                      vec[t["seller"] or ""] * vec[t.get("buyer_before") or ""]]) for t in turns])
        if x.shape[1] != model["mean"].shape[0]:
            return {}   # another embedder (a test's fake one): the weights don't fit it
        scores = 1 / (1 + np.exp(-(((x - model["mean"]) / model["std"]) @ model["weights"].T + model["biases"])))
    except Exception:   # no meaning model here: the review goes out without the flags
        logger.exception("blemish model unavailable")
        return {}
    covered = cfg.get("covered_by", {})
    out: dict[int, list[dict]] = {}
    for i, t in enumerate(turns):
        for j, label in enumerate(str(lbl) for lbl in model["labels"]):
            if not model["enabled"][j] or scores[i, j] < model["thresholds"][j]:
                continue
            if set(covered.get(label, [])) & set(t.get("signals", [])):
                continue   # the rules already said it
            out.setdefault(t["turn"], []).append(
                {"label": label, "reason": cfg["reasons"][label], "confidence": round(float(scores[i, j]), 2)})
    return out
