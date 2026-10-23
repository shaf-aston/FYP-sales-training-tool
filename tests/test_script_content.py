"""Every shipped script file loads, is wired end to end, and uses only known blanks."""
import json
import re

import pytest

from core.loader import CONFIG_DIR, load_yaml
from core.script_engine.engine import advance, start
from core.script_engine.fill import offer_blanks
from core.script_engine.method import ANY, load_common_sense, load_method, load_offer

METHODS = sorted(p.stem for p in (CONFIG_DIR / "methods").glob("*.yaml"))
OFFER_BLANKS = {"months", "price", "setter", "pillar_1", "pillar_2", "pillar_3"}
BLANK = re.compile(r"\{(\w+)\}")


def _lines(step):
    """Every line the step may say. A `say` with a plain twin is checked by the twin: its blanks
    may be missing (the shared matrix uses CAT's answers), and then the plain line is said."""
    return [step.say_plain or step.say, *step.probes, *(r.ack for r in step.routes)]


@pytest.mark.parametrize("name", METHODS)
def test_method_is_connected(name):
    method = load_method(name)  # the loader fails on a step nothing leads to
    assert any(not s.listen for s in method.steps.values()), "no ending step"
    assert method.objections and not method.steps[method.follow_up].listen


@pytest.mark.parametrize("name", METHODS)
def test_blanks_are_known_and_captured_before_use(name):
    method = load_method(name)
    captured = {s.capture for s in method.steps.values() if s.capture}
    numbers = load_yaml("script/engine.yaml")["number_blanks"]
    captured |= {blank for blank, rule in numbers.items() if rule.get("from") in captured}  # "2 years" counted in months
    for step in method.steps.values():
        for line in _lines(step):
            unknown = set(BLANK.findall(line)) - captured - OFFER_BLANKS
            assert not unknown, f"{name} step {step.id}: {unknown}"


@pytest.mark.parametrize("name", METHODS)
def test_walk_to_the_end(name, fake_embedder):
    method = load_method(name)
    move = start(method)
    for _ in range(len(method.steps)):
        if not method.steps[move.state.step].listen:  # the end: nothing left to listen for
            break
        step = method.steps[move.state.step]
        takes_any = any(r.label == ANY for r in step.listen)  # a plain answer; labelled routes may turn back
        label = None if takes_any else next((r.label for r in step.listen if r.examples), None)
        move = advance(method, move.state, label, "an answer")
    assert not method.steps[move.state.step].listen


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
    assert sense.interruptions


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
def test_early_objection_lines_use_only_offer_blanks(name):
    method = load_method(name)  # said before the prospect has answered anything
    known = set(offer_blanks(load_offer("shay_coaching")))
    for line in [o.early for o in method.objections.values()]:
        assert not set(BLANK.findall(line)) - known, line


@pytest.mark.parametrize("name", METHODS)
def test_no_scripted_line_is_a_canned_fair_enough(name):
    # live: "Fair enough." came straight after the prospect said they barely see their daughter
    for step in load_method(name).steps.values():
        assert all(r.ack != "Fair enough." for r in step.routes), step.id
