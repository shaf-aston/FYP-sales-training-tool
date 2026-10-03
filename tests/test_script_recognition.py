"""Slice 3: the real embedder against the public labelled replies. Opt-in (downloads a model)."""
import os
import statistics
import time
from pathlib import Path

import pytest
import yaml

from core.loader import load_yaml
from core.script_engine.embedder import make_embedder
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.recognise import recognise

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)"
)

ROOT = Path(__file__).parent.parent
MIN_ACCURACY = 0.85
MIN_OFF_TOPIC = 0.80
MAX_MEDIAN_MS = 50


def _step_labels(method, step_id):
    return {r.signal: list(r.examples) for r in method.steps[step_id].listen if r.examples}


def _objection_labels(method):
    return {k: list(o.examples) for k, o in method.objections.items()}


def _contexts():
    cat, impact = load_method("cat"), load_method("impact_formula")
    return {
        "step_01": _step_labels(cat, "01"),
        "step_18": _step_labels(cat, "18"),
        "step_19": _step_labels(cat, "19"),
        "objections_cat": _objection_labels(cat),
        "objections_impact": _objection_labels(impact),
        "facts": {k: list(f.examples) for k, f in load_offer("shay_coaching").facts.items()},
        "common_sense": {
            k: list(i.examples) for k, i in load_common_sense().interruptions.items()
        },
    }


@pytest.fixture(scope="module")
def results():
    cfg = load_yaml("selling.yaml")
    embedder = make_embedder(cfg, ROOT)
    data = yaml.safe_load((ROOT / "tests/data/script_replies.yaml").read_text(encoding="utf-8"))
    rows, times = [], []
    for context, labels in _contexts().items():
        for expected, replies in data[context].items():
            for reply in replies:
                start = time.perf_counter()
                match = recognise(
                    reply, labels, embedder, cfg["threshold"], cfg["margin"], cfg["close_call_k"]
                )
                times.append((time.perf_counter() - start) * 1000)
                rows.append((context, reply, expected, match))
    return rows, times


def _got(match):
    return match.label or "none"


def test_labelled_set_is_big_enough(results):
    assert len(results[0]) >= 150


def test_accuracy_and_off_topic(results, capsys):
    rows, _ = results
    on = [r for r in rows if r[2] != "none"]
    off = [r for r in rows if r[2] == "none"]
    # A close call goes to the judge or a probe, so it is not a confident wrong answer.
    correct = sum(_got(m) == exp or m.close for _, _, exp, m in on)
    flagged = sum(m.label is None or m.close for _, _, _, m in off)
    wrong = [(c, r, e, _got(m)) for c, r, e, m in rows if _got(m) != e and not m.close]
    with capsys.disabled():
        print(f"\nrows {len(rows)}  accuracy {correct}/{len(on)}  off-topic flagged {flagged}/{len(off)}")
        for w in wrong:
            print("  WRONG", w)
    assert correct / len(on) >= MIN_ACCURACY
    assert flagged / len(off) >= MIN_OFF_TOPIC


@pytest.mark.parametrize("context, negated", [("step_18", "unclear"), ("step_19", "hesitant")])
def test_negations_never_confidently_wrong(results, context, negated):
    rows = [r for r in results[0] if r[0] == context and r[2] == negated]
    assert len(rows) >= 10
    for _, reply, _, match in rows:
        assert match.label == negated or match.close or match.label is None, (reply, match)
        assert match.label != "agrees", (reply, match)


def test_latency(results, capsys):
    median = statistics.median(results[1])
    with capsys.disabled():
        print(f"\nmedian recognise {median:.1f} ms")
    assert median <= MAX_MEDIAN_MS
