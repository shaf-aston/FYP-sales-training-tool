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
    return Ear(CFG, CAT, load_offer("shay_coaching"), sense, listener, shrugs, lambda *_: "vague")


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


@pytest.mark.parametrize("pick, heard_as", [("money objection", "objection:money"), ("vague", "answer")])
def test_a_grey_band_objection_before_the_price_is_the_ais_call(fake_embedder, pick, heard_as):
    from core.buy_mode.script_engine.hear.recognise import Match

    class GreyBand(Listener):  # the embedder put "money" at 0.81: under the early-objection floor, over the judge's line
        def interruption(self, *a):
            return None

        def match(self, *a, **k):
            return Match("money", 0.81, ("money",), False)

    sense, listener = load_common_sense(), GreyBand(CFG, fake_embedder)
    ear = Ear(CFG, CAT, load_offer("shay_coaching"), sense, listener, Shrugs(CFG, sense, listener, lambda t, s: t),
              lambda reply, candidates: pick)  # "vague": AI down or unsure, so an answer as before
    assert ear.hear("10k seems like a lot", ScriptState(step="03"), False).heard_as.startswith(heard_as)


# A reply with an answer and a question or worry beside it ("3 years, what about you?"): which part leads.
# Fields: kind, name, the text heard as the answer, the side part, the question asked.
@pytest.mark.parametrize("step, text, heard", [
    ("19", "yeah I'm in, how do I pay?", ("answer", "", "how do I pay?", "", "")),   # the question picks the answer
    ("19", "not yet, how do I pay?", ("answer", "", "not yet, how do I pay?", "", "")),   # "not yet" takes it back
    ("19", "no, how do I pay?", ("answer", "", "no, how do I pay?", "", "")),
    ("22", "no, credit?", ("answer", "", "no, credit?", "", "")),
    ("14", "that's a lot, how do I pay?", ("ready", "pays", None, "", "")),   # a worry beside it: not alone
    ("03", "3 years, what about you?", ("answer", "", "3 years", "question", "what about you?")),
    ("03", "about 3 years, is this a scam?", ("answer", "", "about 3 years", "objection:scam", "is this a scam?")),
    ("01", "more money, how long is the course?", ("answer", "", "more money", "fact:length", "how long is the course?")),
    ("05", "nothing, why do you ask?", ("answer", "", "nothing", "question", "why do you ask?")),
    ("03", "3 years, can you say that again?", ("question", None, None, "", "")),   # a sense leads, no side
    ("02", "dunno, what about you?", ("question", None, "what about you?", "", "")),   # no answer in the content
    ("03", "shut up, what's the price?", ("fact", "price", None, "", "")),
])
def test_a_side_question_or_worry_is_heard_beside_the_answer(ear, step, text, heard):
    v = ear.hear(text, ScriptState(step=step), opened=step in {"14", "19", "22"})
    got = (v.kind, v.name, v.text, v.side, v.asked)
    assert all(want is None or g == want for g, want in zip(got, heard)), got


@pytest.mark.parametrize("step, text, kind, name", [   # back from "brb": the whole reply, heard as one
    ("19", "yeah I'm in, how do I pay?", "answer", ""), ("03", "3 years, what about you?", "question", None),
    ("03", "about 3 years, is this a scam?", "objection", "scam"), ("01", "more money, how long is the course?", "fact", "length"),
])
def test_after_a_pause_a_reply_is_never_split_into_answer_and_side(ear, step, text, kind, name):
    v = ear.hear(text, ScriptState(step=step, waiting=True), opened=step == "19")
    assert (v.kind, v.side) == (kind, "") and name in {None, v.name}
    assert kind != "answer" or v.text == text


def test_an_early_answer_beside_a_side_question_is_kept(ear):
    v = ear.hear("more money, I want 5k a month, how long is the course?", ScriptState(step="01"), opened=False)
    assert (v.text, v.side, v.ahead.slots) == ("more money, I want 5k a month", "fact:length", {"number": "5k a month"})
    assert ear.hear("freedom, how long is the course?", ScriptState(step="01"), opened=False).ahead is None
