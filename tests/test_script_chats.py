"""Live test chats A-E (round 2) as scenario tests: keen buyer, early number, re-ask wording,
frustration, safe product answers, memory in the ack. Offline: bag-of-words embedder, fake AI.
These prove the wiring; how well the real model hears each phrase is test_script_recognition's job."""
from itertools import pairwise

import pytest

from core.loader import load_yaml
from core.script_engine.engine import ScriptState, asked_line, hear_ahead, jump, move_on
from core.script_engine.method import (
    load_common_sense,
    load_method,
    load_offer,
    parse_method,
)
from core.script_engine.seller import ScriptSeller

CFG = load_yaml("selling.yaml")
CAT = load_method("cat")
SENSE = load_common_sense()
FRUSTRATED = SENSE.interruptions["frustrated"].reply


def down(prompt, max_tokens):
    raise RuntimeError("AI down")


class Recorder:
    """A fake AI: answers with `line` and keeps every prompt."""

    def __init__(self, line="NONE"):
        self.line, self.prompts = line, []

    def __call__(self, prompt, max_tokens):
        self.prompts.append(prompt)
        return self.line


def seller(bow, llm=down, step=None, **state):
    s = ScriptSeller(CFG, CAT, load_offer("shay_coaching"), SENSE, bow, llm)
    if step:
        s.reset(ScriptState(step=step, **state))
    return s


def say(step_id, slots=None):
    step = CAT.steps[step_id]
    return step.say_plain or step.say


# ---- C1/C2 keen buyer (chat A) ---------------------------------------------------------------

READY_Q = CAT.steps["ready"].say
PAY_Q = CAT.steps["22"].say


def test_keen_buyer_is_asked_if_they_know_the_programme(fake_embedder):
    s = seller(fake_embedder)
    text, _ = s.reply("i'm in, send the payment link")
    assert text == READY_Q
    assert s.state.step == "ready"


@pytest.mark.parametrize("answer", ["yes", "yeah"])
def test_keen_buyer_who_knows_it_gets_the_price_and_the_payment_question(fake_embedder, answer):
    s = seller(fake_embedder)
    s.reply("i'm in, send the payment link")
    text, _ = s.reply(answer)
    assert text == f"The investment is $5k. {PAY_Q}"


def test_keen_buyer_who_doesnt_gets_one_line_first(fake_embedder):
    s = seller(fake_embedder)
    s.reply("i'm in, send the payment link")
    text, _ = s.reply("no")
    assert text.startswith("Quick version: it's a 6-month programme with Education & curriculum")
    assert text.endswith(f"The investment is $5k. {PAY_Q}")


def test_price_and_scam_questions_at_the_ready_step_are_answered(fake_embedder):
    s = seller(fake_embedder)
    s.reply("i'm in, send the payment link")
    text, _ = s.reply("what's the price")
    assert "$5k" in text and text.endswith(READY_Q)  # the jump is past the price step on purpose
    text, _ = s.reply("is this a scam")
    assert text == CAT.objections["scam"].loop[0]


def test_the_jump_drops_open_plays_and_parked_worries(fake_embedder):
    s = seller(fake_embedder, step="03", parked=("money",), play="scam")
    s.reply("i'm in, send the payment link")
    assert (s.state.step, s.state.parked, s.state.play) == ("ready", (), "")


@pytest.mark.parametrize("step, text", [("01", "I'm in sales"), ("18", "yes")])
def test_no_false_jump(fake_embedder, step, text):
    s = seller(fake_embedder, step=step)
    s.reply(text)
    assert s.state.step != "ready"


def test_no_jump_from_the_soft_close_on(fake_embedder):
    s = seller(fake_embedder, step="19")
    s.reply("i'm in, send the payment link")
    assert s.state.step != "ready"


def test_the_floor_holds_on_steps_whose_answers_score_low(fake_embedder):
    """Step 01's own answers barely compete with "send the payment link", so only the floor stops a
    middling match from jumping (live: "I'm in sales" on the real model)."""
    from dataclasses import replace
    s = seller(fake_embedder)
    s.reply("send the payment link")                   # ~0.76 here: above the threshold, under the floor
    assert s.state.step != "ready"
    s = seller(fake_embedder)
    s.method = replace(CAT, ready=replace(CAT.ready, min_score=0.0))
    s.reply("send the payment link")
    assert s.state.step == "ready"                     # the same reply, no floor: it jumps


def test_impact_formula_has_no_shortcut():
    assert load_method("impact_formula").ready is None


# ---- C3 a number given early (chat A) --------------------------------------------------------

def test_a_number_given_early_is_kept_and_its_question_skipped(fake_embedder):
    s = seller(fake_embedder)
    text, _ = s.reply("honestly I want 5k a month")   # not an answer to step 01: it digs
    assert text == CAT.steps["01"].probes[0]
    assert s.state.slots["number"] == "5k a month"
    text, _ = s.reply("I want financial freedom")
    assert s.state.step == "03" and text == say("03")


@pytest.mark.parametrize("text", ["I make 2k a month", "I'm 25", "lost 2k on a course",
                                  "I want to quit and I make 2k a month"])
def test_other_numbers_are_not_the_goal(text):
    state = hear_ahead(CAT, ScriptState(step="01"), text)
    assert "number" not in state.slots


def test_the_step_itself_still_captures_normally():
    state = hear_ahead(CAT, ScriptState(step="02"), "I want 5k a month")
    assert "number" not in state.slots  # only later steps are heard ahead


# ---- C4 a side question keeps the words last used (chat C) -----------------------------------

def test_side_question_re_asks_the_probe_it_was_on(fake_embedder):
    s = seller(fake_embedder)
    s.reply("3k")                                    # unrecognised: probe 1
    text, _ = s.reply("is this a bot?")
    assert text.endswith(CAT.steps["01"].probes[0])
    assert CAT.steps["01"].say not in text


def test_asked_line_follows_the_asks():
    assert asked_line(CAT, ScriptState(step="01")) == (CAT.steps["01"].say, "")
    assert asked_line(CAT, ScriptState(step="01", asks=2))[0] == CAT.steps["01"].probes[1]
    assert asked_line(CAT, ScriptState(step="01", asks=9))[0] == CAT.steps["01"].probes[-1]
    assert asked_line(CAT, ScriptState(step="02", asks=1))[0] == CAT.steps["02"].say  # no probes


# ---- C5 frustration (chat C) -----------------------------------------------------------------

def test_frustration_on_a_dig_step_asks_another_way(fake_embedder):
    s = seller(fake_embedder)
    text, _ = s.reply("stop with the script man")
    assert text == f"{FRUSTRATED} {CAT.steps['01'].probes[0]}"


def test_frustration_on_an_open_step_moves_on_without_saving_or_acking(fake_embedder):
    llm = Recorder("I hear that.")
    s = seller(fake_embedder, llm, step="04")
    text, _ = s.reply("this is stupid")
    assert text == f"{FRUSTRATED} {say('05')}"
    assert "why" not in s.state.slots and not llm.prompts  # no AI call either


def test_frustration_never_builds_on_an_answer_they_didnt_give(fake_embedder):
    s = seller(fake_embedder, step="10", slots={"years": "two"})
    text, _ = s.reply("whatever")
    assert "You already have" not in text and s.state.step == "willing"


@pytest.mark.parametrize("text", ["whatever works for me", "I don't care about money, I want time"])
def test_answers_that_sound_close_are_still_answers(fake_embedder, text):
    s = seller(fake_embedder, step="04")
    reply, _ = s.reply(text)
    assert FRUSTRATED not in reply and s.state.slots["why"] == text


def test_frustration_has_its_own_floor(fake_embedder):
    from dataclasses import replace
    s = seller(fake_embedder)
    text, _ = s.reply("stop with the script")            # ~0.89: over the floor
    assert text.startswith(FRUSTRATED)
    calm = replace(SENSE.interruptions["frustrated"], min_score=0.95)
    s = seller(fake_embedder)
    s.sense = replace(SENSE, interruptions={**SENSE.interruptions, "frustrated": calm})
    text, _ = s.reply("stop with the script")
    assert not text.startswith(FRUSTRATED)


def test_hostile_chat_never_says_the_same_line_twice_in_a_row(fake_embedder):
    s = seller(fake_embedder)
    said = [s.opening()[0]]
    for text in ["3k", "stop with the script man", "whatever", "this is stupid",
                 "f*** off with the questions"]:
        said.append(s.reply(text)[0])
    assert all(a != b for a, b in pairwise(said)), said


def test_move_on_with_nowhere_to_go_asks_again():
    move = move_on(CAT, ScriptState(step="end"))
    assert move.state.step == "end"


# ---- C6 uncovered product questions (chats B, D) ---------------------------------------------

FALLBACK = CFG["uncovered_fallback"]


@pytest.mark.parametrize("line", [
    "Most people make their first sale within 8 weeks.",     # a made-up number
    "We guarantee you'll make it back.",                     # a promise
    "Yes, there's a free trial for students.",               # a made-up policy
    "It's $5k, which pays for itself.",                      # the price before step 14
    "NOT_COVERED",
    "Not covered.",
])
def test_unsafe_product_answers_fall_back(fake_embedder, line):
    s = seller(fake_embedder, Recorder(line), step="03")
    text, _ = s.reply("how long till my first sale?")
    assert text.startswith(FALLBACK)


def test_a_clean_product_answer_may_go_beyond_the_fact_words(fake_embedder):
    line = "You learn step by step with direct coaching, so you never piece it together alone."
    llm = Recorder(line)
    s = seller(fake_embedder, llm, step="03", slots={"outcome": "time with my kids"})
    text, _ = s.reply("what would i learn?")
    assert text.startswith(line) and text.endswith(say("03"))
    assert "time with my kids" in llm.prompts[0]          # what they told us
    assert "piecing it together" in llm.prompts[0]        # the offer's `about`
    assert "$5k" not in llm.prompts[0]                    # no price before the price step


# ---- C7 memory in the ack (chats D, night shift) ---------------------------------------------

def test_ack_may_link_to_an_earlier_answer(fake_embedder):
    llm = Recorder("Two years for more time with your kids.")
    s = seller(fake_embedder, llm, step="03", slots={"outcome": "I want more time with my kids"})
    text, _ = s.reply("two years")
    assert "<earlier>" in llm.prompts[0] and "more time with my kids" in llm.prompts[0]
    assert text == f"Two years for more time with your kids. {say('04')}"


def test_ack_without_that_memory_cannot_use_those_words(fake_embedder):
    llm = Recorder("Two years for more time with your kids.")
    s = seller(fake_embedder, llm, step="03")
    text, _ = s.reply("two years")
    assert text == say("04") and "<earlier>" not in llm.prompts[0]


# ---- C10 the new moves cost no AI calls ------------------------------------------------------

def test_jump_and_move_on_ask_no_ai(fake_embedder):
    llm = Recorder()
    seller(fake_embedder, llm).reply("i'm in, send the payment link")
    seller(fake_embedder, llm, step="04").reply("this is stupid")
    assert llm.prompts == []


def test_jump_is_pure():
    before = ScriptState(step="03", parked=("money",))
    move = jump(CAT, before, "ready")
    assert before.parked == ("money",) and move.state.parked == ()


# ---- the YAML is checked on load -------------------------------------------------------------

def _mini(**extra):
    steps = {
        "a": {"ui_stage": "intent", "say": "A?", "capture": "x", "listen": {"any": {"then": "b"}}},
        "b": {"ui_stage": "intent", "say": "Done."},
    }
    steps["a"].update(extra.pop("a", {}))
    return {"first": "a", "price_step": "a", "steps": steps, **extra}


@pytest.mark.parametrize("data, error", [
    (_mini(a={"answered_by": r"\d+"}), "answer"),
    (_mini(a={"answered_by": r"(?P<answer>\d+)", "capture": ""}), "capture"),
    (_mini(ready={"examples": ["x"], "then": "a", "until": "b", "min_score": 0.8}), "until"),
])
def test_loader_rejects_bad_shortcuts(data, error):
    with pytest.raises(ValueError, match=error):
        parse_method("bad", data)


def test_loader_rejects_an_unknown_after():
    from core.script_engine.method import parse_common_sense
    data = {"bring_back": "", "park": "", "revisit": "",
            "interruptions": {"x": {"examples": ["x"], "reply": "ok", "after": "sing"}}}
    with pytest.raises(ValueError, match="after"):
        parse_common_sense(data)
