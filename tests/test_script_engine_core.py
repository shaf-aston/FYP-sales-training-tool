"""Slice 1: method loading, pure engine, recognition. No model, no network."""
import re
from pathlib import Path

import pytest
import yaml

from core.script_engine.engine import ScriptState, advance, start
from core.script_engine.method import load_method, load_offer, parse_method
from core.script_engine.recognise import recognise

FIXTURES = Path(__file__).parent / "fixtures" / "script_engine"
ENGINE_DIR = Path(__file__).parent.parent / "core" / "script_engine"


@pytest.fixture
def mini():
    return load_method("mini", FIXTURES)


def _labels(method, step_id):
    return {r.signal: list(r.examples) for r in method.steps[step_id].listen if r.examples}


def _turn(method, state, reply, embedder):
    labels = _labels(method, state.step)
    signal = recognise(reply, labels, embedder, 0.5, 0.03, 3).label if labels else None
    return advance(method, state, signal, reply)


def _run(method, replies, embedder):
    move = start(method)
    texts = [move.text_template]
    for reply in replies:
        move = _turn(method, move.state, reply, embedder)
        texts.append(move.text_template)
    return texts, move


def test_full_conversation(mini, fake_embedder):
    texts, move = _run(
        mini, ["I want to grow my business", "yes that makes sense"], fake_embedder
    )
    assert texts == [
        "What would you like to achieve?",
        "So you want {goal}. Does that make sense?",   # silent step skipped
        "Good. Great, next steps.",
    ]
    assert move.done and move.ui_stage == "outcome"
    assert move.state.slots["goal"] == "I want to grow my business"
    assert move.state.last_point == "I want to grow my business"


def test_unmatched_reply_repeats_step(mini, fake_embedder):
    move = _turn(mini, start(mini).state, "purple banana", fake_embedder)
    assert move.text_template == "What would you like to achieve?"
    assert move.state.step == "a" and not move.state.slots


def test_replay_is_deterministic(mini, fake_embedder):
    replies = ["purple banana", "I want more freedom", "yes"]
    assert _run(mini, replies, fake_embedder)[0] == _run(mini, replies, fake_embedder)[0]


def test_state_is_not_mutated(mini, fake_embedder):
    before = start(mini).state
    advance(mini, before, "clear", "reply")
    assert before == ScriptState(step="a")


def test_loader_rejects_broken_graphs():
    good = yaml.safe_load((FIXTURES / "mini.yaml").read_text(encoding="utf-8"))
    for mutate, text in [
        (lambda d: d.update(first="zzz"), "first step"),
        (lambda d: d["steps"]["a"]["listen"]["clear"].update(then="nope"), "unknown then"),
        (lambda d: d["steps"]["a"].update(ui_stage="bogus"), "ui_stage"),
        (lambda d: d["steps"]["silent"].update(listen={}), "silent step"),
    ]:
        data = yaml.safe_load(yaml.safe_dump(good))
        mutate(data)
        with pytest.raises(ValueError, match=text):
            parse_method("bad", data)


def test_loader_rejects_duplicate_step_ids(tmp_path):
    (tmp_path / "dup.yaml").write_text(
        'first: "a"\nsteps:\n  "a": {ui_stage: logical, say: x}\n  "a": {ui_stage: logical, say: y}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_method("dup", tmp_path)


def test_offer_loads():
    offer = load_offer("mini_offer", FIXTURES)
    assert offer.months == 3 and offer.facts["where"].answer == "All around the world."


def test_recognise_close_call_and_threshold(fake_embedder):
    labels = {"yes": ["yes sounds good"], "no": ["no not for me"]}
    hit = recognise("yes sounds good", labels, fake_embedder, 0.65, 0.03, 3)
    assert hit.label == "yes" and not hit.close and hit.candidates[0] == "yes"
    miss = recognise("purple banana", labels, fake_embedder, 0.65, 0.03, 3)
    assert miss.label is None
    both = recognise("yes not", {"a": ["yes x"], "b": ["not x"]}, fake_embedder, 0.1, 0.5, 3)
    assert both.close


def test_engine_code_names_no_method_or_offer():
    banned = re.compile(r"\b(cat|impact|formula|shay|coaching|freedom|pillar)\b", re.IGNORECASE)
    for path in ENGINE_DIR.glob("*.py"):
        assert not banned.search(path.read_text(encoding="utf-8")), path.name


def test_loader_rejects_yaml_boolean_route_names():
    data = yaml.safe_load((FIXTURES / "mini.yaml").read_text(encoding="utf-8"))
    data["steps"]["b"]["listen"][True] = data["steps"]["b"]["listen"].pop("agrees")
    with pytest.raises(TypeError, match="not text"):
        parse_method("bad", data)
