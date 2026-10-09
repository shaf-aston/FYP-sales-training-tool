"""Every shipped script file loads, is wired end to end, and uses only known blanks."""
import json
import re

import pytest

from core.loader import CONFIG_DIR
from core.script_engine.engine import advance, start
from core.script_engine.fill import offer_blanks
from core.script_engine.method import ANY, load_common_sense, load_method, load_offer

METHODS = sorted(p.stem for p in (CONFIG_DIR / "methods").glob("*.yaml"))
OFFER_BLANKS = {"months", "price", "setter", "pillar_1", "pillar_2", "pillar_3"}
BLANK = re.compile(r"\{(\w+)\}")


def _reachable(method):
    seen, todo = set(), [method.first] + ([method.ready.then] if method.ready else [])
    while todo:
        step_id = todo.pop()
        if step_id not in seen:
            seen.add(step_id)
            todo += [r.then for r in method.steps[step_id].routes]
    return seen


def _lines(step):
    return [step.say, *step.probes, *(r.ack for r in step.routes)]


@pytest.mark.parametrize("name", METHODS)
def test_method_is_connected(name):
    method = load_method(name)
    assert _reachable(method) == set(method.steps)
    assert any(not s.listen for s in method.steps.values()), "no ending step"
    assert method.objections and all(len(o.loop) == 2 for o in method.objections.values())


@pytest.mark.parametrize("name", METHODS)
def test_blanks_are_known_and_captured_before_use(name):
    method = load_method(name)
    captured = {s.capture for s in method.steps.values() if s.capture}
    for step in method.steps.values():
        for line in _lines(step):
            unknown = set(BLANK.findall(line)) - captured - OFFER_BLANKS
            assert not unknown, f"{name} step {step.id}: {unknown}"


@pytest.mark.parametrize("name", METHODS)
def test_walk_to_the_end(name, fake_embedder):
    method = load_method(name)
    move = start(method)
    for _ in range(len(method.steps)):
        if move.done:
            break
        step = method.steps[move.state.step]
        takes_any = any(r.label == ANY for r in step.listen)  # a plain answer; labelled routes may turn back
        label = None if takes_any else next((r.label for r in step.listen if r.examples), None)
        move = advance(method, move.state, label, "an answer")
    assert move.done


def test_cat_has_all_numbered_steps():
    ids = set(load_method("cat").steps)
    assert {f"{n:02d}" for n in range(23)} <= ids


def test_cat_step_07_is_silent():
    assert load_method("cat").steps["07"].say == ""


def test_offer_and_common_sense_load():
    offer = load_offer("shay_coaching")
    assert offer.months == 6 and len(offer.pillars) == 3
    assert "all around the world" in offer.facts["location"].answer
    sense = load_common_sense()
    assert "{last_point}" in sense.bring_back and sense.interruptions


@pytest.mark.parametrize("name", METHODS)
def test_nothing_in_the_script_asks_any_questions(name):
    text = json.dumps(load_method(name), default=lambda o: o.__dict__).lower()
    assert "any questions" not in text


@pytest.mark.parametrize("name", METHODS)
def test_every_prospect_blank_has_a_plain_line(name):
    known = set(offer_blanks(load_offer("shay_coaching")))
    for step in load_method(name).steps.values():
        blanks = set(BLANK.findall(step.say)) - known
        if blanks:
            assert step.say_plain, f"{name} step {step.id} needs say_plain"
            assert not set(BLANK.findall(step.say_plain)) - known


@pytest.mark.parametrize("name", METHODS)
def test_objection_lines_use_only_offer_blanks(name):
    method = load_method(name)
    known = set(offer_blanks(load_offer("shay_coaching")))
    lines = [method.follow_up] + [x for o in method.objections.values() for x in (*o.loop, o.direct)]
    for line in lines:
        assert not set(BLANK.findall(line)) - known, line


@pytest.mark.parametrize("name", METHODS)
def test_no_scripted_line_is_a_canned_fair_enough(name):
    # live: "Fair enough." came straight after the prospect said they barely see their daughter
    for step in load_method(name).steps.values():
        assert all(r.ack != "Fair enough." for r in step.routes), step.id
