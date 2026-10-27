"""The verdict: what a reply was heard as, checked without saying anything back."""
import pytest

from core.infra.loader import load_yaml
from core.buy_mode.script_engine.engine import ScriptState
from core.buy_mode.script_engine.method import load_common_sense, load_method, load_offer
from core.buy_mode.script_engine.hear.recognise import Listener
from core.buy_mode.script_engine.hear.shrug import Shrugs
from core.buy_mode.script_engine.hear.verdict import Ear

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")


@pytest.fixture
def ear(fake_embedder):
    sense, listener = load_common_sense(), Listener(CFG, fake_embedder)
    shrugs = Shrugs(CFG, sense, listener, lambda t, slots: t)
    return Ear(CFG, CAT, load_offer("shay_coaching"), sense, listener, shrugs)


@pytest.mark.parametrize("text, state, heard_as", [
    ("ok, what's next?", ScriptState(step="04"), "nudge"),
    ("ok", ScriptState(step="04"), "says_nothing"),
    ("brb", ScriptState(step="04"), "sense:pause"),
    ("ok", ScriptState(step="04", waiting=True), "answer"),            # back from "brb": not a shrug
    ("it's my kids", ScriptState(step="04"), "answer"),
])
def test_heard_as(ear, text, state, heard_as):
    assert ear.hear(text, state, opened=False).heard_as == heard_as


def test_a_worry_already_in_its_branch_is_heard_as_the_answer(ear):
    said = "it's too expensive"
    assert ear.hear(said, ScriptState(step="m_funded"), opened=True).heard_as == "objection:money"
    assert ear.hear(said, ScriptState(step="m_funded", raised=("money",)), opened=True).kind != "objection"


def test_a_worry_the_step_asks_about_is_its_answer_not_a_new_objection(ear):
    # "what do you need to think over: the money...?" -> "it's too expensive" names the branch, not a 2nd worry
    v = ear.hear("it's too expensive", ScriptState(step="m_think_what", raised=("think",)), opened=True)
    assert v.kind != "objection"


def test_a_nudge_is_cut_off_and_the_rest_heard(ear):
    v = ear.hear("my kids, what's next?", ScriptState(step="04"), opened=False)
    assert v.text == "my kids" and v.kind == "answer"


def test_an_early_answer_rides_on_the_verdict_not_on_the_seller(ear):
    v = ear.hear("I want to make 5k a month", ScriptState(step="01"), opened=False)
    assert v.ahead is not None and v.ahead.slots
    assert ear.hear("how much do I need to make 5k a month?", ScriptState(step="01"), opened=False).ahead is None
