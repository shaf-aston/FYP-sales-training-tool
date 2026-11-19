"""The second layer under the turn rules (core/training/blemish.py): it only adds flags, says nothing the rules
already said, and steps aside when it can't run."""

import os

import numpy as np
import pytest

from core.training import blemish

DIM = 4


class Embedder:
    """Fixed vectors: lines with "worry" point one way, the rest another."""

    def embed(self, texts):
        return [np.array([1, 0, 0, 0] if "worry" in t else [0, 1, 0, 0], dtype=np.float32) for t in texts]


def model(enabled=(True, True)):
    """Two blemishes: 'dismissive' fires on the "worry" direction, 'pushy' on everything (to test covered_by)."""
    w = np.zeros((2, DIM * 3), dtype=np.float32)
    w[0, 0] = 20.0
    return {"labels": np.array(["dismissive", "pushy"]), "weights": w, "biases": np.array([-10.0, 10.0], dtype=np.float32),
            "thresholds": np.array([0.9, 0.9], dtype=np.float32), "enabled": np.array(enabled),
            "mean": np.zeros(DIM * 3, dtype=np.float32), "std": np.ones(DIM * 3, dtype=np.float32)}


def turn(n, seller, signals=()):
    return {"turn": n, "seller": seller, "buyer_before": "I'm not sure.", "signals": list(signals)}


@pytest.fixture
def wired(monkeypatch):
    def wire(m):
        monkeypatch.setattr(blemish, "_model", lambda: m)
        monkeypatch.setattr("core.infra.embedder.shared_embedder", lambda: Embedder())
    return wire


def test_it_flags_what_it_was_trained_on_and_adds_a_plain_reason(wired):
    wired(model(enabled=(True, False)))
    got = blemish.notice([turn(1, "Oh, don't worry about that."), turn(2, "What would help most?")])
    assert list(got) == [1] and got[1][0]["label"] == "dismissive"
    assert got[1][0]["reason"].startswith("Also noticed:") and 0.9 <= got[1][0]["confidence"] <= 1


def test_nothing_the_rules_already_said(wired):
    wired(model(enabled=(False, True)))
    got = blemish.notice([turn(1, "Sign today.", ["pressure"]), turn(2, "Sign today, honestly.")])
    assert list(got) == [2]   # turn 1's pressure signal already says pushy


def test_a_blemish_switched_off_in_the_model_never_shows(wired):
    wired(model(enabled=(False, False)))
    assert blemish.notice([turn(1, "Oh, don't worry about that.")]) == {}


def test_without_a_model_or_with_another_embedder_the_review_goes_out_without_flags(monkeypatch, wired):
    monkeypatch.setattr(blemish, "_model", lambda: None)
    assert blemish.notice([turn(1, "Oh, don't worry about that.")]) == {}
    m = model()
    m["mean"] = np.zeros(999, dtype=np.float32)   # weights for a different vector size
    wired(m)
    assert blemish.notice([turn(1, "Oh, don't worry about that.")]) == {}


def test_a_broken_embedder_never_breaks_the_review(monkeypatch):
    monkeypatch.setattr(blemish, "_model", lambda: model())

    def broken():
        raise RuntimeError("no model files")
    monkeypatch.setattr("core.infra.embedder.shared_embedder", broken)
    assert blemish.notice([turn(1, "Oh, don't worry about that.")]) == {}


def test_the_shipped_model_matches_the_shipped_embedder():
    m = blemish._model()
    assert m is not None, "models/blemish.npz is missing: run python -m scripts.blemish.train"
    assert str(m["embed_model"]) == "BAAI/bge-small-en-v1.5" and m["mean"].shape == (384 * 3,)
    assert m["enabled"].any()


@pytest.mark.skipif(os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)")
def test_the_real_model_reads_a_call_like_a_coach(monkeypatch):
    from core.infra.embedder import make_embedder
    from core.infra.env import ROOT_DIR
    from core.infra.loader import load_yaml
    real = make_embedder(load_yaml("script/engine.yaml"), ROOT_DIR)
    monkeypatch.setattr("core.infra.embedder.shared_embedder", lambda: real)   # conftest swaps in a fake one
    calls = [turn(1, "Great. So what CRM are you using?"), turn(2, "Oh don't worry about that, everyone feels like that at first."),
             turn(3, "How long has it been just you?")]
    calls[0]["buyer_before"] = "My business partner just quit, so it's all on me now."
    got = blemish.notice(calls)
    assert got[1][0]["label"] == "ignored" and got[2][0]["label"] == "dismissive" and 3 not in got
