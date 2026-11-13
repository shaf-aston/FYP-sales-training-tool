"""Train the blemish model: a second layer under the turn rules that flags what they miss when it is said in other
words (pushy, dismissive, leading, ignored, feature_dump; scripts/blemish/examples.py).

    .venv/bin/python -m scripts.blemish.train

The app's own embedder (core/infra/embedder.py, bge-small) turns the buyer's line and the seller's reply into
vectors; one logistic regression per blemish reads [seller, buyer, seller*buyer] (the product lets "ignored" see
whether the reply engages with what was said). Plain numpy, so the app needs nothing new to run it.

Each blemish gets a threshold from 5-fold cross-validation: the lowest score whose out-of-fold precision is at
least MIN_PRECISION (a false flag teaches the wrong lesson, so precision comes first). Then the separately written
TEST set is scored once; a blemish whose test precision is under MIN_TEST_PRECISION ships switched off. Writes
models/blemish.npz (weights, thresholds, which are on) and models/blemish.json (the numbers, for the record).
"""

from __future__ import annotations

import json
import random

import numpy as np

from core.infra.embedder import make_embedder
from core.infra.env import ROOT_DIR
from core.infra.loader import load_yaml
from scripts.blemish.examples import BUYER, CLEAN, IGNORED, LABELS, TEST, TRAIN

MIN_PRECISION = 0.90
MIN_TEST_PRECISION = 0.75
OUT = ROOT_DIR / "models"
SEED = 7


def dataset() -> list[tuple[str, str, set[str]]]:
    """(buyer line, seller line, blemishes). Lines whose blemish does not depend on what was said are paired with
    three different buyer lines; ignored and clean pairs keep their own buyer line (that is what makes them so)."""
    rng = random.Random(SEED)
    rows = []
    for label, lines in TRAIN.items():
        for line in lines:
            for buyer in rng.sample(BUYER, 3):
                rows.append((buyer, line, {label}))
    rows += [(b, s, {"ignored"}) for b, s in IGNORED]
    rows += [(b, s, set()) for b, s in CLEAN]
    return rows


CACHE = ROOT_DIR / ".cache" / "blemish_vectors.npz"   # gitignored: the vectors of the example lines, for quick re-runs


def features(embed, pairs: list[tuple[str, str]]) -> np.ndarray:
    texts = sorted({t for pair in pairs for t in pair})
    cached = dict(np.load(CACHE, allow_pickle=True)["v"].item()) if CACHE.exists() else {}
    fresh = [t for t in texts if t not in cached]
    if fresh:
        cached.update(zip(fresh, (np.asarray(v, dtype=np.float32) for v in embed.embed(fresh))))
        CACHE.parent.mkdir(exist_ok=True)
        np.savez_compressed(CACHE, v=np.array(cached, dtype=object))
    vec = {t: cached[t] for t in texts}
    rows = []
    for buyer, seller in pairs:
        s, b = vec[seller], vec[buyer]
        rows.append(np.concatenate([s, b, s * b]))
    return np.stack(rows)


def fit(x: np.ndarray, y: np.ndarray, l2: float = 1e-3, epochs: int = 600, lr: float = 0.5) -> tuple[np.ndarray, float]:
    """Logistic regression by gradient descent, positives weighted up to balance the classes."""
    w, b = np.zeros(x.shape[1], dtype=np.float64), 0.0
    pos = max(1.0, y.sum())
    weight = np.where(y == 1, (len(y) - pos) / pos, 1.0)
    weight = weight / weight.mean()
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-(x @ w + b)))
        g = (p - y) * weight
        w -= lr * (x.T @ g / len(y) + l2 * w)
        b -= lr * g.mean()
    return w, b


def score(x: np.ndarray, w: np.ndarray, b: float) -> np.ndarray:
    return 1 / (1 + np.exp(-(x @ w + b)))


def threshold_for(p: np.ndarray, y: np.ndarray) -> tuple[float | None, float, float]:
    """The lowest threshold with precision >= MIN_PRECISION (and its precision, recall), or None."""
    for t in np.arange(0.30, 0.99, 0.01):
        hit = p >= t
        if hit.sum() == 0:
            break
        precision = (hit & (y == 1)).sum() / hit.sum()
        if precision >= MIN_PRECISION:
            return float(round(t, 2)), float(precision), float((hit & (y == 1)).sum() / max(1, (y == 1).sum()))
    return None, 0.0, 0.0


def main() -> None:
    cfg = load_yaml("script/engine.yaml")
    embed = make_embedder(cfg, ROOT_DIR)
    rows = dataset()
    x = features(embed, [(b, s) for b, s, _ in rows])
    xt = features(embed, [(b, s) for b, s, _ in TEST])
    mean, std = x.mean(0), x.std(0) + 1e-6
    x, xt = (x - mean) / std, (xt - mean) / std

    rng = np.random.default_rng(SEED)
    fold = rng.integers(0, 5, len(rows))
    weights, biases, thresholds, enabled, report = [], [], [], [], {}
    for label in LABELS:
        y = np.array([1.0 if label in labels else 0.0 for _, _, labels in rows])
        oof = np.zeros(len(rows))
        for k in range(5):
            w, b = fit(x[fold != k], y[fold != k])
            oof[fold == k] = score(x[fold == k], w, b)
        t, cv_p, cv_r = threshold_for(oof, y)
        w, b = fit(x, y)
        yt = np.array([1 if label in labels else 0 for _, _, labels in TEST])
        pt = score(xt, w, b)
        hit = pt >= (t if t is not None else 2.0)
        test_p = float((hit & (yt == 1)).sum() / hit.sum()) if hit.sum() else 0.0
        test_r = float((hit & (yt == 1)).sum() / max(1, yt.sum()))
        on = bool(t is not None and test_p >= MIN_TEST_PRECISION and hit.sum() > 0)
        weights.append(w)
        biases.append(b)
        thresholds.append(t if t is not None else 1.0)
        enabled.append(on)
        false_flags = [TEST[int(i)][1] for i in np.where(hit & (yt == 0))[0]]
        report[label] = {"train_examples": int(y.sum()), "threshold": t, "cv_precision": round(cv_p, 3),
                         "cv_recall": round(cv_r, 3), "test_examples": int(yt.sum()), "test_precision": round(test_p, 3),
                         "test_recall": round(test_r, 3), "enabled": on, "test_false_flags": false_flags}
        print(f"{label:13} thr {t}  cv P {cv_p:.2f} R {cv_r:.2f}  test P {test_p:.2f} R {test_r:.2f}  "
              f"({int(yt.sum())} in test)  {'ON' if on else 'off'}  false: {false_flags}")

    clean_test = [i for i, (_, _, labels) in enumerate(TEST) if not labels]
    flagged_clean = sum(1 for i in clean_test if any(
        enabled[j] and score(xt[i:i + 1], weights[j], biases[j])[0] >= thresholds[j] for j in range(len(LABELS))))
    report["clean_test_turns_flagged"] = f"{flagged_clean} of {len(clean_test)}"
    print("clean test turns wrongly flagged:", report["clean_test_turns_flagged"])

    OUT.mkdir(exist_ok=True)
    np.savez_compressed(OUT / "blemish.npz", labels=np.array(LABELS), weights=np.stack(weights).astype(np.float32),
                        biases=np.array(biases, dtype=np.float32), thresholds=np.array(thresholds, dtype=np.float32),
                        enabled=np.array(enabled), mean=mean.astype(np.float32), std=std.astype(np.float32),
                        embed_model=np.array(cfg["embed_model"]))
    (OUT / "blemish.json").write_text(json.dumps({"embed_model": cfg["embed_model"], "min_precision": MIN_PRECISION,
                                                  "labels": report}, indent=2))
    print("wrote", OUT / "blemish.npz")


if __name__ == "__main__":
    main()
