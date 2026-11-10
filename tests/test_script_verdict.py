"""The verdict: what a reply was heard as, checked without saying anything back."""
import pytest

from core.infra.loader import load_yaml
from core.buy_mode.script_engine.engine import ScriptState, question_of
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
    ("ok", ScriptState(step="04", waiting=True), "sense:back"),        # back from "brb": not a shrug, nor the answer (round 78: saved as it)
    ("my kids", ScriptState(step="04", waiting=True), "answer"),         # guard: an answer after a pause is the answer
    ("it's my kids", ScriptState(step="04"), "answer"),
    ("let me think about it", ScriptState(step="19"), "objection:think"),   # round 14: the worry, word for word
    ("I don't know", ScriptState(step="19"), "answer"),                     # not knowing, never a worry
])
def test_heard_as(ear, text, state, heard_as):
    assert ear.hear(text, state, opened=state.step == "19").heard_as.startswith(heard_as)


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


def _grey_band_ear(fake_embedder, judge, score=0.81, matched=None):
    from core.buy_mode.script_engine.hear.recognise import Match

    class GreyBand(Listener):  # the embedder put "money" at 0.81: under the early-objection floor, over the judge's line
        def interruption(self, *a):
            return None

        def match(self, text, labels, **k):
            if matched is not None:
                matched.append((text, labels))
            return Match("money", score, ("money",), False)

    sense, listener = load_common_sense(), GreyBand(CFG, fake_embedder)
    return Ear(CFG, CAT, load_offer("shay_coaching"), sense, listener, Shrugs(CFG, sense, listener, lambda t, s: t), judge)


@pytest.mark.parametrize("pick, heard_as", [("money objection", "objection:money"), ("vague", "answer")])
def test_a_grey_band_objection_before_the_price_is_the_ais_call(fake_embedder, pick, heard_as):
    ear = _grey_band_ear(fake_embedder, lambda reply, candidates: pick)  # "vague": AI down or unsure, so an answer
    assert ear.hear("10k seems like a lot", ScriptState(step="03"), False).heard_as.startswith(heard_as)


def test_the_ai_judges_a_grey_band_worry_against_the_question_asked(fake_embedder):
    asked = []
    ear = _grey_band_ear(fake_embedder, lambda reply, options: asked.append((reply, options)) or "vague")
    ear.hear("10k seems like a lot", ScriptState(step="03"), False)
    question = question_of(CAT.steps["03"].say_plain or CAT.steps["03"].say)
    assert asked == [("10k seems like a lot", {"money objection": ["money"], "answer": [f"answering '{question}'"]})]


def test_the_grey_band_is_matched_on_the_early_worries_and_their_nearest_examples(fake_embedder):
    """The worry is picked from what counts before the price, and the AI is shown that worry's nearest examples."""
    matched = []
    ear = _grey_band_ear(fake_embedder, lambda *a: "vague", matched=matched)
    ear.hear("10k seems like a lot", ScriptState(step="03"), False)
    early = {k: o.heard(False) for k, o in CAT.objections.items()}
    text, labels = matched[-2]
    assert text == "10k seems like a lot" and set(labels) <= set(early) and labels["money"] == early["money"]
    assert matched[-1] == ("10k seems like a lot", {e: [e] for e in early["money"]})


def test_a_worry_right_on_the_judges_line_is_judged(fake_embedder):
    asked = []
    ear = _grey_band_ear(fake_embedder, lambda *a: asked.append(a) or "money objection",
                         score=CFG["early_objection_judge_score"])
    assert ear.hear("10k seems like a lot", ScriptState(step="03"), False).heard_as.startswith("objection:money") and asked


def test_a_worry_under_the_judges_line_is_not_judged(fake_embedder):
    asked = []
    ear = _grey_band_ear(fake_embedder, lambda *a: asked.append(a) or "money objection",
                         score=CFG["early_objection_judge_score"] - 0.01)
    assert ear.hear("10k seems like a lot", ScriptState(step="03"), False).heard_as == "answer" and not asked


# A reply with an answer and a question or worry beside it ("3 years, what about you?"): which part leads.
# Fields: kind, name, the text heard as the answer, the side part, the question asked.
@pytest.mark.parametrize("step, text, heard", [
    ("19", "yeah I'm in, how do I pay?", ("answer", "", "how do I pay?", "", "")),   # the question picks the answer
    ("19", "not yet, how do I pay?", ("answer", "", "not yet, how do I pay?", "", "")),   # "not yet" takes it back
    ("19", "no, how do I pay?", ("answer", "", "no, how do I pay?", "", "")),
    ("22", "no, credit?", ("answer", "", "no, credit?", "", "")),
    ("14", "that's a lot, how do I pay?", ("ready", "pays", None, "", "")),   # a worry beside it: not alone
    ("19", "I don't have the money, how do I pay?", ("objection", "money", "I don't have the money", "", "")),  # not ready
    ("03", "3 years, which team won?", ("answer", "", "3 years", "question", "which team won?")),
    ("03", "3 years, what about you?", ("answer", "", "3 years", "sense:about_me", "what about you?")),   # round 14
    ("03", "about 3 years, is this a scam?", ("answer", "", "about 3 years", "objection:scam", "is this a scam?")),
    ("01", "more money, how long is the course?", ("answer", "", "more money", "fact:length", "how long is the course?")),
    ("05", "nothing, why do you ask?", ("answer", "", "nothing", "sense:why_ask", "why do you ask?")),   # round 10: the reason, not "I'll find out"
    ("02", "dunno, which team won?", ("question", None, "which team won?", "", "")),   # no answer in the content
    ("02", "dunno, what about you?", ("sense", "about_me", "what about you?", "", "")),   # round 14: the honest line
    ("03", "shut up, what's the price?", ("fact", "price", None, "", "")),
])
def test_a_side_question_or_worry_is_heard_beside_the_answer(ear, step, text, heard):
    v = ear.hear(text, ScriptState(step=step), opened=step in {"14", "19", "22"})
    got = (v.kind, v.name, v.text, v.side, v.asked)
    assert all(want is None or g == want for g, want in zip(got, heard)), got
    assert v.asking == (v.kind != "objection")  # the worry is heard on its own: the question beside it is dropped


@pytest.mark.parametrize("step, text, said", [
    ("03", "3 years, can you say that again?", "3 years"),   # round 73 callers: "come again? 2k" lost the 2k
    ("02", "come again? 2k", "2k"), ("05", "what was the question? money", "money"),
])
def test_an_answer_beside_a_say_that_again_is_kept_with_no_side(ear, step, text, said):
    v = ear.hear(text, ScriptState(step=step), opened=False)
    assert (v.kind, v.text, v.side) == ("answer", said, "")


def test_say_that_again_alone_still_says_it_again(ear):
    v = ear.hear("can you say that again?", ScriptState(step="03"), opened=False)
    assert v.kind != "answer"   # guard: no answer beside it


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


@pytest.mark.parametrize("step, text, kind", [   # "3 years?" to "how long?" is the answer said with a rise
    ("03", "3 years?", "answer"), ("03", "a year?", "answer"), ("02", "5k a month?", "answer"),
    ("goal_practical", "freedom?", "answer"), ("goal_practical", "um, my family?", "answer"),
    ("goal_practical", "3 years?", "question"),   # a figure is not a goal: they ask
    ("02", "freedom?", "question"), ("03", "freedom?", "question"),   # not the step's shape
    ("01", "3 years?", "question"),   # a step with no shape: a rise asks
    ("04", "because money is nice?", "answer"),   # whole calls: a reason said with a rise was a question
    ("01", "cos I need it?", "answer"),   # any step: "because ..." never asks
])
def test_a_short_reply_with_a_rise_is_the_answer_when_it_has_the_steps_shape(ear, step, text, kind):
    assert ear.hear(text, ScriptState(step=step), opened=False).kind == kind


@pytest.mark.parametrize("unsure, heard_as", [(0.9, "objection:think"), (1.0, "answer")])
def test_a_hedge_is_the_worry_only_when_it_is_nearer_the_worry(ear, monkeypatch, unsure, heard_as):
    """Round 14: "let me think about it" (1.0 to the think-it-over worry, 0.96 to "let me think") at the close
    was heard as a shrug. A hedge just as near not knowing as the worry stays a hedge."""
    monkeypatch.setattr(ear._shrugs, "unsure", lambda text: unsure)
    v = ear.hear("let me think about it", ScriptState(step="19"), opened=True)
    assert v.heard_as.startswith(heard_as), v.heard_as



@pytest.mark.parametrize("text", ["whichever", "up to you", "either", "i don't mind", "Whichever!"])
def test_a_choice_left_to_us_is_heard_as_the_steps_either(ear, text):
    # round 87 callers: "whichever" to "credit or debit?" was asked again until the call left the close
    assert ear.hear(text, ScriptState(step="22"), opened=True).text == CAT.steps["22"].either


@pytest.mark.parametrize("text", ["the second one", "the first one", "second one please", "the latter", "the other one", "Option 2"])
def test_a_pick_by_place_is_heard_as_the_steps_either(ear, text):
    # round 88 callers: "the second one" to "credit or debit?" was asked again until the call left the close
    assert ear.hear(text, ScriptState(step="22"), opened=True).text == CAT.steps["22"].either


@pytest.mark.parametrize("step, text", [("22", "ok"), ("22", "idk"), ("01", "whichever"), ("22", "whichever card"), ("01", "the second one"), ("22", "the second card")])
def test_only_a_choice_left_to_us_at_a_step_with_an_either_is_turned(ear, step, text):
    assert ear.hear(text, ScriptState(step=step), opened=True).text != "either is fine"   # guards


@pytest.mark.parametrize("step, text, heard_as", [
    ("05", "stopping me how? dunno", "question"), ("04", "the reason for what? dunno", "question"),   # a question word is asked, not wondered
    ("04", "for what? dunno", "sense:clarify"), ("03", "since when?", "sense:clarify"),   # round 87 probes: a word and a question word asks what we meant
    ("03", "a long long time? dunno", "answer"),   # three words are more than a word or two said back: the unsure answer
])
def test_only_a_word_or_two_with_no_question_word_is_wondered_aloud(ear, step, text, heard_as):
    # mutation 89: both limits on a wondered-aloud rise had no test
    assert ear.hear(text, ScriptState(step=step), opened=False).heard_as == heard_as
