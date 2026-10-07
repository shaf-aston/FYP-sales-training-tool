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
                                  "I want to quit and I make 2k a month",
                                  "I want to leave my job paying 2k a month",
                                  "I need more than the 2k a month I get now",
                                  "I don't want to pay 500 a month for a course",
                                  "I need to save 200 a month"])
def test_other_numbers_are_not_the_goal(text):
    state = hear_ahead(CAT, ScriptState(step="01"), text)
    assert "number" not in state.slots


def test_a_question_about_a_figure_is_not_their_goal(fake_embedder):
    s = seller(fake_embedder)
    s.reply("do i need 5k a month to start?")
    assert "number" not in s.state.slots


@pytest.mark.parametrize("text", ["i need to stop paying 1500 a month for my car",
                                  "i want to cancel the 300 a month gym"])
def test_spending_is_not_the_goal(text):
    assert "number" not in hear_ahead(CAT, ScriptState(step="01"), text).slots


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


def test_frustration_drops_an_open_objection_play(fake_embedder):
    """Live-style: they push back on a loop question; the play must not swallow their next answer."""
    s = seller(fake_embedder, step="15", play="scam", objection_counts={"scam": 1})
    s.reply("stop with the script man")
    assert s.state.step == "16" and s.state.play == ""
    s.reply("yes sounds good")
    assert s.state.step == "17"


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
    "You get 6 coaching calls and lifetime access.",         # a known number counting something new
    "Our students all earn a full-time income.",             # a result
    "No, there is no contract.",                             # a made-up policy
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


def test_no_fact_sheet_means_no_ai_answer(fake_embedder):
    from dataclasses import replace
    llm = Recorder("Anything.")
    s = seller(fake_embedder, llm, step="03")
    s.offer = replace(s.offer, about="")
    text, _ = s.reply("will refunds exist?")
    assert text.startswith(FALLBACK) and not llm.prompts


def test_the_price_joins_the_fact_sheet_only_once_open(fake_embedder):
    llm = Recorder("NOT_COVERED")
    seller(fake_embedder, llm, step="03").reply("will refunds exist?")
    seller(fake_embedder, llm, step="15").reply("will refunds exist?")
    assert "$5k" not in llm.prompts[0] and "The investment is $5k." in llm.prompts[1]


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


READY = {"examples": ["x"], "then": "b", "until": "b", "min_score": 0.8}


@pytest.mark.parametrize("data, error", [
    (_mini(a={"answered_by": r"\d+"}), "answer"),
    (_mini(a={"answered_by": r"(?P<answer>\d*)"}), "empty"),
    (_mini(ready={**READY, "examples": []}), "examples"),
    (_mini(ready={**READY, "min_score": 5}), "min_score"),
    (_mini(ready={k: v for k, v in READY.items() if k != "min_score"}), "min_score"),
    (_mini(a={"answered_by": r"(?P<answer>\d+)", "capture": ""}), "capture"),
    (_mini(ready={"examples": ["x"], "then": "a", "until": "b", "min_score": 0.8}), "until"),
])
def test_loader_rejects_bad_shortcuts(data, error):
    with pytest.raises(ValueError, match=error):
        parse_method("bad", data)


def test_loader_rejects_a_shortcut_that_leads_back():
    data = _mini(ready={**READY, "until": "b"})
    data["steps"]["b"] = {"ui_stage": "intent", "say": "B?", "listen": {"any": {"then": "a"}}}
    data["steps"]["a"]["listen"] = {"any": {"then": "b"}}
    with pytest.raises(ValueError, match="before until"):
        parse_method("bad", data)


@pytest.mark.parametrize("item", [{"after": "sing"}, {"wait": True}, {"min_score": -1}])
def test_loader_rejects_bad_interruptions(item):
    from core.script_engine.method import parse_common_sense
    data = {"bring_back": "", "park": "", "revisit": "",
            "interruptions": {"x": {"examples": ["x"], "reply": "ok", **item}}}
    with pytest.raises(ValueError):
        parse_common_sense(data)


def test_loader_rejects_an_unknown_after():
    from core.script_engine.method import parse_common_sense
    data = {"bring_back": "", "park": "", "revisit": "",
            "interruptions": {"x": {"examples": ["x"], "reply": "ok", "after": "sing"}}}
    with pytest.raises(ValueError, match="after"):
        parse_common_sense(data)


# ---- C11 payment: only a way to pay ends the call (review follow-up 1) -----------------------

WELCOME = CAT.steps["end"].say
SOFT_CLOSE = CAT.steps["19"].say
BACK_OUT = CAT.steps["22"].listen[1].ack


@pytest.mark.parametrize("step", ["20", "22"])
@pytest.mark.parametrize("text", ["actually no, forget it", "no, I changed my mind", "no"])
def test_backing_out_goes_back_to_the_soft_close(fake_embedder, step, text):
    s = seller(fake_embedder, step=step)
    reply, _ = s.reply(text)
    assert reply == f"{BACK_OUT} {SOFT_CLOSE}"
    assert s.state.step == "19"


@pytest.mark.parametrize("text", ["credit", "debit please", "card"])
def test_a_way_to_pay_ends_the_call(fake_embedder, text):
    s = seller(fake_embedder, step="22")
    reply, _ = s.reply(text)
    assert reply == WELCOME and s.state.step == "end"


def test_an_unclear_payment_reply_is_asked_again_then_goes_back_never_welcomed(fake_embedder):
    s = seller(fake_embedder, step="22")
    reply, _ = s.reply("hmm")
    assert reply == CAT.steps["22"].probes[0]
    reply, _ = s.reply("hmm")
    assert reply == SOFT_CLOSE and WELCOME not in reply


def test_a_worry_at_payment_is_still_looped(fake_embedder):
    s = seller(fake_embedder, step="22")
    reply, _ = s.reply("I need to think about it")
    assert reply == CAT.objections["think"].loop[0]


def test_a_reason_at_self_resell_still_moves_on(fake_embedder):
    s = seller(fake_embedder, step="20")
    reply, _ = s.reply("because I'm sick of my job")
    assert reply.endswith(PAY_Q) and s.state.slots["reason"] == "because I'm sick of my job"


def test_keen_buyer_who_backs_out_at_payment_is_not_welcomed(fake_embedder):
    s = seller(fake_embedder)
    s.reply("i'm in, send the payment link")
    s.reply("yes")
    reply, _ = s.reply("actually no, forget it")
    assert WELCOME not in reply and s.state.step == "19"


# ---- C12 a question that still answers the step (review follow-up 2) -------------------------

def test_an_answer_with_a_question_in_it_is_an_answer(fake_embedder):
    s = seller(fake_embedder, step="18")
    reply, _ = s.reply("yeah makes sense, what's next?")
    assert reply == SOFT_CLOSE and s.state.step == "19"
    assert CFG["uncovered_fallback"] not in reply


def test_a_real_product_question_is_still_answered(fake_embedder):
    ai = Recorder("NOT_COVERED")
    s = seller(fake_embedder, ai, step="18")
    reply, _ = s.reply("yeah but how long is it?")
    assert reply.startswith(CFG["uncovered_fallback"]) and s.state.step == "18"
    assert any("<question>" in p for p in ai.prompts)


class ByPrompt:
    """A fake AI that answers product questions with `answer` and everything else with "NONE"."""

    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def __call__(self, prompt, max_tokens):
        self.prompts.append(prompt)
        return self.answer if "<facts>" in prompt else "NONE"


def test_an_answer_with_a_product_question_gets_both(fake_embedder):
    s = seller(fake_embedder, ByPrompt("You just need a laptop and wifi."), step="18")
    reply, _ = s.reply("yeah it all makes sense, do I need a laptop?")
    assert reply == f"You just need a laptop and wifi. {SOFT_CLOSE}" and s.state.step == "19"


def test_an_answer_with_a_question_the_facts_dont_cover_just_moves_on(fake_embedder):
    s = seller(fake_embedder, ByPrompt("NOT_COVERED"), step="18")
    reply, _ = s.reply("yeah makes sense, what's next?")
    assert CFG["uncovered_fallback"] not in reply and s.state.step == "19"


def test_a_near_miss_answer_with_a_question_stays_a_question(fake_embedder):
    s = seller(fake_embedder, step="18")   # under the threshold: their question is never dropped on a guess
    reply, _ = s.reply("yes that makes sense, but do I need a laptop?")
    assert reply.startswith(CFG["uncovered_fallback"]) and s.state.step == "18"


def test_a_mixed_payment_reply_is_judged_never_welcomed_on_a_guess(fake_embedder):
    s = seller(fake_embedder, step="22")   # "no, credit?": pays and backs out too close to call, AI down
    reply, _ = s.reply("no, credit?")
    assert reply == CAT.steps["22"].probes[0] and s.state.step == "22"


GO_ON = SENSE.interruptions["go_on"].reply


@pytest.mark.parametrize("step, then", [("15", "16"), ("16", "17")])
def test_whats_next_on_a_pitch_line_moves_on(fake_embedder, step, then):
    s = seller(fake_embedder, step=step)
    reply, _ = s.reply("ok, what's next?")
    assert reply.startswith(f"{GO_ON} ") and reply.endswith(CAT.steps[then].say.split(":", 1)[1])
    assert s.state.step == then


@pytest.mark.parametrize("step", ["18", "19", "22"])
def test_whats_next_on_a_step_that_needs_an_answer_asks_it_another_way(fake_embedder, step):
    s = seller(fake_embedder, step=step)
    reply, _ = s.reply("what's next?")
    assert reply == f"{GO_ON} {CAT.steps[step].probes[0]}" and s.state.step == step


def test_whats_next_is_never_saved_as_an_answer(fake_embedder):
    s = seller(fake_embedder, step="20")
    s.reply("what's next?")
    assert "reason" not in s.state.slots and s.state.step == "22"


def test_whats_next_asks_no_ai(fake_embedder):
    ai = Recorder()
    seller(fake_embedder, ai, step="15").reply("ok, what's next?")
    assert ai.prompts == []
