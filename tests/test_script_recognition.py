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
MAX_CONFIDENT_WRONG = 0.03
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
    embedder.warm([e for labels in _contexts().values() for ex in labels.values() for e in ex])
    rows, times = [], []
    for context, labels in _contexts().items():
        for expected, replies in data[context].items():
            for reply in replies:
                start = time.perf_counter()
                match = recognise(
                    reply, labels, embedder, cfg["threshold"], cfg["margin"], cfg["close_call_k"],
                    cfg["near_miss"],
                )
                times.append((time.perf_counter() - start) * 1000)
                rows.append((context, reply, expected, match))
    return rows, times


def _got(match):
    return match.label or "none"


def test_labelled_set_is_big_enough(results):
    assert len(results[0]) >= 150


def test_accuracy_off_topic_and_confident_wrong(results, capsys):
    rows, _ = results
    on = [r for r in rows if r[2] != "none"]
    off = [r for r in rows if r[2] == "none"]
    strict = sum(_got(m) == exp and not m.close for _, _, exp, m in on)
    close = sum(m.close for _, _, _, m in rows)
    wrong = [(c, r, e, _got(m)) for c, r, e, m in rows if _got(m) != e and not m.close]
    flagged = sum(m.label is None or m.close for _, _, _, m in off)
    with capsys.disabled():
        print(f"\nrows {len(rows)}  strict top-1 {strict}/{len(on)} = {strict / len(on):.1%}"
              f"  close-call rate {close}/{len(rows)} = {close / len(rows):.1%}"
              f"  confident-wrong {len(wrong)}/{len(rows)} = {len(wrong) / len(rows):.1%}"
              f"  off-topic flagged {flagged}/{len(off)}")
        for w in wrong:
            print("  WRONG", w)
    assert strict / len(on) >= MIN_ACCURACY
    assert len(wrong) / len(rows) <= MAX_CONFIDENT_WRONG
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


def test_combined_interruption_set_picks_the_right_group(capsys):
    """The seller matches interruptions, facts and objections in one pass: groups must not steal."""
    cfg = load_yaml("selling.yaml")
    embedder = make_embedder(cfg, ROOT)
    ctxs = _contexts()
    embedder.warm([e for labels in ctxs.values() for ex in labels.values() for e in ex])
    labels = {}
    for group, key in (("sense", "common_sense"), ("fact", "facts"), ("objection", "objections_cat")):
        labels.update({f"{group}:{k}": v for k, v in ctxs[key].items()})
    data = yaml.safe_load((ROOT / "tests/data/script_replies.yaml").read_text(encoding="utf-8"))
    rows = [
        (f"{group}:{label}", reply)
        for group, key in (("sense", "common_sense"), ("fact", "facts"), ("objection", "objections_cat"))
        for label, replies in data[key].items() if label != "none"
        for reply in replies
    ]
    hits = 0
    for expected, reply in rows:
        m = recognise(reply, labels, embedder, cfg["threshold"], cfg["margin"],
                      cfg["close_call_k"], cfg["near_miss"])
        hits += m.label == expected or m.close
        if m.label != expected and not m.close:
            with capsys.disabled():
                print("  MIXED UP", reply, "->", m.label, "expected", expected)
    with capsys.disabled():
        print(f"\ncombined {hits}/{len(rows)}")
    assert hits / len(rows) >= MIN_ACCURACY


def test_only_script_examples_are_remembered_never_replies():
    embedder = make_embedder(load_yaml("selling.yaml"), ROOT)
    embedder.warm(["I want freedom"])
    embedder.embed(["I want freedom", "a prospect reply nobody will ever warm"])
    assert list(embedder._seen) == ["I want freedom"]


def _down(prompt, max_tokens):
    raise RuntimeError("AI down")


@pytest.mark.parametrize("replies, expected_step", [
    # plain answers to the step's own question: never an interruption or a product question
    (["I just want freedom, to stop working for someone else and travel", "maybe 8k a month"], "03"),
    (["I want freedom", "10k a month", "about two years now"], "04"),
    (["I want freedom", "10k a month", "two years", "because I hate missing time with my kids"], "05"),
    (["I want freedom", "ok cool, about 10k", "three years"], "04"),
])
def test_answers_move_the_script_on(replies, expected_step):
    from core.script_engine.seller import ScriptSeller

    cfg = load_yaml("selling.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    for text in replies:
        seller.reply(text)
    assert seller.state.step == expected_step


def test_real_price_question_still_gets_the_early_answer():
    from core.script_engine.seller import ScriptSeller

    cfg = load_yaml("selling.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    seller.reply("I want freedom")
    text, _ = seller.reply("wait, sorry, what's this going to cost me?")
    assert "first a couple of questions" in text and seller.state.step == "02"
