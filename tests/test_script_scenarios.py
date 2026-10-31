"""Live test chats A-E (round 2) as scenario tests: keen buyer, early number, re-ask wording,
frustration, safe product answers, memory in the ack. Offline: bag-of-words embedder, fake AI.
These prove the wiring; how well the real model hears each phrase is test_script_recognition's job."""
import json
from itertools import pairwise

import pytest

from core.infra.loader import load_yaml
from core.buy_mode.script_engine.engine import ScriptState, asked_line, hear_ahead, jump, move_on
from core.buy_mode.script_engine.method import (
    load_common_sense,
    load_method,
    load_offer,
    parse_method,
)
from core.buy_mode.script_engine.seller import ScriptSeller

CFG = load_yaml("script/engine.yaml")
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
        if "<goal>" in prompt:  # the listen call: they answered, `line` is the ack
            return f"ANSWERED: yes\nACK: {self.line}\nPROBE: none"
        return self.line


def seller(bow, llm=down, step=None, method=CAT, sense=SENSE, offer=None, **state):
    s = ScriptSeller(CFG, method, offer or load_offer("shay_coaching"), sense, bow, llm)
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
    assert text == CAT.steps[CAT.objections["scam"].enter].say


def test_the_jump_drops_parked_worries(fake_embedder):
    s = seller(fake_embedder, step="03", parked=("money",))
    s.reply("i'm in, send the payment link")
    assert (s.state.step, s.state.parked) == ("ready", ())


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
    s = seller(fake_embedder, method=replace(CAT, ready=replace(CAT.ready, min_score=0.0)))
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
    s.reply("I want financial freedom")              # level 1: dug into, not yet 02
    s.reply("so I can stop stressing every time I buy something")
    text, _ = s.reply("I'd finally be proud of myself")
    assert s.state.step == "03" and text == say("03")


@pytest.mark.parametrize("text", ["I want to quit my job, travel, and have 10k a month",
                                  "I want to be having 8k a month"])
def test_a_goal_sentence_with_have_keeps_the_number(text):
    state = hear_ahead(CAT, ScriptState(step="01"), text)
    assert state.slots.get("number", "").endswith("a month")


@pytest.mark.parametrize("text", ["I make 2k a month", "I have 2k a month now", "I'm 25", "lost 2k on a course",
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
    s.reply("not sure really")                       # vague, nothing to ask about: probe 1
    text, _ = s.reply("is this a bot?")
    assert text.endswith(CAT.steps["01"].probes[0])
    assert CAT.steps["01"].say not in text


def test_asked_line_follows_the_asks():
    assert asked_line(CAT, ScriptState(step="01")) == (CAT.steps["01"].say, "")
    assert asked_line(CAT, ScriptState(step="01", asks=1))[0] == CAT.steps["01"].probes[0]
    assert asked_line(CAT, ScriptState(step="01", asks=9))[0] == CAT.steps["01"].probes[-1]
    assert asked_line(CAT, ScriptState(step="05", asks=1))[0] == CAT.steps["05"].say  # no probes


# ---- C5 frustration (chat C) -----------------------------------------------------------------

def test_frustration_on_a_dig_step_asks_another_way(fake_embedder):
    s = seller(fake_embedder)
    text, _ = s.reply("stop with the script man")
    assert text == f"{FRUSTRATED} {CAT.steps['01'].probes[0]}"


def test_frustration_on_an_open_step_moves_on_without_saving_or_acking(fake_embedder):
    llm = Recorder("I hear that.")
    s = seller(fake_embedder, llm, step="08")
    text, _ = s.reply("this is stupid")
    assert text == f"{FRUSTRATED} {say("09")}"
    assert "gap" not in s.state.slots and not llm.prompts  # no AI call either


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
    s = seller(fake_embedder, sense=replace(SENSE, interruptions={**SENSE.interruptions, "frustrated": calm}))
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
    s = seller(fake_embedder, llm, step="03", offer=replace(load_offer("shay_coaching"), about=""))
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
    s = seller(fake_embedder, llm, step="04", slots={"outcome": "I want more time with my kids"})
    text, _ = s.reply("two years of the same job")
    assert "<earlier>" in llm.prompts[0] and "more time with my kids" in llm.prompts[0]
    assert text.startswith("Two years for more time with your kids. What's the reason")


def test_ack_without_that_memory_cannot_use_those_words(fake_embedder):
    llm = Recorder("Two years for more time with your kids.")
    s = seller(fake_embedder, llm, step="04")
    text, _ = s.reply("two years of the same job")
    assert text.startswith("What's the reason") and "<earlier>" not in llm.prompts[0]


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
    from core.buy_mode.script_engine.method import parse_common_sense
    data = {"park": "", "revisit": "",
            "interruptions": {"x": {"examples": ["x"], "reply": "ok", **item}}}
    with pytest.raises(ValueError):
        parse_common_sense(data)


def test_loader_rejects_an_unknown_after():
    from core.buy_mode.script_engine.method import parse_common_sense
    data = {"park": "", "revisit": "",
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


def test_a_worry_at_payment_enters_its_matrix_branch(fake_embedder):
    s = seller(fake_embedder, step="22")
    reply, _ = s.reply("I need to think about it")
    assert reply == CAT.steps[CAT.objections["think"].enter].say


def test_a_yes_with_its_reason_after_is_heard_as_yes(fake_embedder):
    s = seller(fake_embedder, step="m_funded")
    reply, _ = s.reply("yes, the course looks like exactly what I need right now")
    assert reply == CAT.steps["m_funded_why"].say


@pytest.mark.parametrize("said", ["um", "I just need some time"])
def test_no_logistics_named_is_asked_again_never_taken_as_the_answer(fake_embedder, said):
    s = seller(fake_embedder, step="m_think_what")
    s.reply(said)
    assert s.state.step == "m_think_what"


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
    s = seller(fake_embedder, step="18")   # a near miss, whole and by part: their question is never dropped on a guess
    reply, _ = s.reply("sort of makes sense, do I need a laptop?")
    assert reply.startswith(CFG["uncovered_fallback"]) and s.state.step == "18"


def test_a_mixed_payment_reply_is_judged_never_welcomed_on_a_guess(fake_embedder):
    s = seller(fake_embedder, step="22")   # "no, credit?": pays and backs out too close to call, AI down
    reply, _ = s.reply("no, credit?")
    assert reply == CAT.steps["22"].probes[0] and s.state.step == "22"


GO_ON = SENSE.nudge


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


# ---- C13 their own words in the line, by rule (no AI) ----------------------------------------

@pytest.mark.parametrize("reply, phrase", [
    ("financial freedom", "financial freedom"),
    ("I want financial freedom", "financial freedom"),
    ("honestly I just want freedom", "freedom"),
    ("just like more money", "more money"),  # filler "like" is never said back
    ("Financial freedom!", "financial freedom"),
    ("more time with family", "more time with family"),
    ("time in Dubai", "time in Dubai"),
    ("I want to be my own boss", "be your own boss"),  # verb goal, the line picks its verb form
    ("my own boss", "your own boss"),            # first person turned to second
    ("freedom for me and my whole family", None),  # too long
    ("travel more", "travel more"),
    ("fine. more money obviously", "more money"),   # live: said back whole
    ("not sure really", None),
    ("", None),
])
def test_echo_phrase(reply, phrase):
    from core.buy_mode.script_engine.words.fill import echo_phrase
    assert echo_phrase(reply, CFG) == phrase


def test_their_outcome_goes_back_into_the_next_question(fake_embedder):
    s = seller(fake_embedder, step="01")
    reply, _ = s.reply("I want financial freedom")
    assert reply == "What are you hoping to achieve with financial freedom?"
    s.reply("so I can stop stressing every time I buy something")
    reply, _ = s.reply("I'd finally be proud of myself")
    assert reply == "How much would you need to be making each month to have financial freedom?"


def test_a_goal_as_an_action_is_dug_into_by_being_able_to(fake_embedder):
    s = seller(fake_embedder, step="01")
    reply, _ = s.reply("I want to make more money")
    assert reply == "What are you hoping to achieve by being able to make more money?"


def test_a_goal_already_at_level_2_or_3_skips_the_rungs_it_climbed(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.reply("so I can stop stressing every time I buy something")
    assert s.state.step == "goal_identity"
    s = seller(fake_embedder, step="01")
    s.reply("I want to be someone my kids can look up to")
    assert s.state.step == "02"


FRUIT = parse_method("fruit", {"first": "a", "price_step": "z", "steps": {
    "a": {"ui_stage": "intent", "say": "Which fruit?", "unsure": "apple", "stuck": {"then": "z"}, "listen": {
        "apple": {"examples": ["red apple"], "then": "y"},
        "pear": {"examples": ["red pear"], "then": "z"},
        "grape": {"examples": ["green grape"], "then": "z"},
        "plum": {"examples": ["blue plum"], "then": "a", "keep": False}}},   # the "vague, ask again" route
    "y": {"ui_stage": "intent", "say": "Apple then."},
    "z": {"ui_stage": "intent", "say": "Done."}}})


@pytest.mark.parametrize("reply, step", [
    ("red apple pear", "y"),                # apple and pear tie, both real answers: the safe one, not asked again
    ("red apple blue plum", "a"),           # might be the ask-again route: asked again
    ("red apple pear fig kiwi", "a"),       # nothing clears the bar: asked again
])
def test_a_close_call_nobody_settles(fake_embedder, reply, step):
    s = seller(fake_embedder, method=FRUIT, step="a")   # AI down: the judge can't settle it
    s.reply(reply)
    assert s.state.step == step


def test_a_close_call_that_might_be_vague_is_still_asked_again(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.reply("more money and I want to make money online")
    assert s.state.step == "01"


def test_a_surface_goal_again_on_the_practical_rung_is_asked_another_way(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.reply("more money")
    reply, _ = s.reply("more money")
    assert s.state.step == "goal_practical" and reply == CAT.steps["goal_practical"].probes[0]
    assert s.state.slots["outcome"] == "more money"   # the first answer stays theirs


def test_words_that_dont_fit_get_the_plain_line(fake_embedder):
    s = seller(fake_embedder, step="01")
    reply, _ = s.reply("I want to quit my job and be my own boss")
    assert reply == CAT.steps["goal_practical"].say_plain


def test_a_vague_answer_is_never_said_back(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.reply("not sure really")
    assert "outcome" not in s.state.slots


def test_backing_out_is_not_kept_as_their_reason(fake_embedder):
    s = seller(fake_embedder, step="20")
    s.reply("actually no, forget it")
    assert "reason" not in s.state.slots


# ---- C14 a nudge on the end of a reply (review: "yes, what's next?" lost the yes) ------------

@pytest.mark.parametrize("step, text, then", [
    ("18", "yes, what's next?", "19"),
    ("18", "yeah, so what's next", "19"),
    ("22", "credit, what's next?", "end"),
    ("22", "visa, then what?", "end"),
    ("17", "yeah, definitely open to that, what's next?", "18"),
    ("20", "because I want freedom, what's next?", "21"),
])
def test_the_rest_of_a_nudged_reply_is_its_answer(fake_embedder, step, text, then):
    s = seller(fake_embedder, step=step)
    reply, _ = s.reply(text)
    assert CFG["uncovered_fallback"] not in reply
    assert s.state.step == then or (then == "21" and s.state.step == "22")  # 21 runs on into 22


def test_a_nudged_reason_is_kept_without_the_nudge(fake_embedder):
    s = seller(fake_embedder, step="20")
    s.reply("because I want freedom, what's next?")
    assert s.state.slots["reason"] == "because I want freedom"


@pytest.mark.parametrize("text", ["what's next for me after the programme?", "I want to go on holiday more"])
def test_a_nudge_word_inside_a_reply_is_not_a_nudge(fake_embedder, text):
    s = seller(fake_embedder, step="15")
    reply, _ = s.reply(text)
    assert not reply.startswith(f"{GO_ON} ")


@pytest.mark.parametrize("nudge, error", [
    ({"reply": "Sure?", "phrases": ["go on"]}, "must not ask"),
    ({"reply": "Sure."}, "both"),
])
def test_loader_rejects_a_bad_nudge(nudge, error):
    from core.buy_mode.script_engine.method import parse_common_sense
    data = {"park": "", "revisit": "", "interruptions": {}, "nudge": nudge}
    with pytest.raises(ValueError, match=error):
        parse_common_sense(data)


def test_loader_rejects_echo_without_a_capture():
    with pytest.raises(ValueError, match="echo"):
        parse_method("x", {"first": "a", "price_step": "a", "steps": {
            "a": {"ui_stage": "intent", "say": "hi", "echo": True, "listen": {"any": {"then": "a"}}}}})


@pytest.mark.parametrize("reply, number", [
    ("about 5 years now", "5"),
    ("two years", "2"),
    ("a year", "1"),
    ("about a year now", "1"),
    ("a couple of years", "2"),
    ("6 months", None),      # wrong unit, the years line is dropped
    ("ages", None),
    ("", None),
])
def test_number_phrase(reply, number):
    from core.buy_mode.script_engine.words.fill import number_phrase
    assert number_phrase(reply, CFG["number_blanks"]["years"], CFG) == number


@pytest.mark.parametrize("reply, months", [("a year", "12"), ("a couple of years", "24"), ("six months", "6"), ("a month", "1"), ("ages", None)])
def test_months_thinking_counts_the_answer_in_months(reply, months):
    from core.buy_mode.script_engine.words.fill import number_phrase
    assert number_phrase(reply, CFG["number_blanks"]["months_thinking"], CFG) == months


def test_years_line_fills_from_their_answer():
    from core.buy_mode.script_engine.words.fill import Filler
    line = "You already have for {years} years."
    offer = type("Offer", (), {"months": 6, "price": "£1", "industry": "", "setter": "", "pillars": []})()
    filler = Filler(CFG, offer, frozenset())
    assert filler.fill(line, {"years": "probably 3 years"}) == "You already have for 3 years."
    assert filler.fill(line, {"years": "a while"}) is None


@pytest.mark.parametrize("reply, phrase", [
    ("financialy freedom", "financial freedom"),
    ("I want finanical fredom", "financial freedom"),
    ("time in Dubai", "time in Dubai"),   # a place name is not "fixed"
    ("more time", "more time"),           # short words are left alone
])
def test_echo_phrase_fixes_typos(reply, phrase):
    from core.buy_mode.script_engine.words.fill import echo_phrase
    assert echo_phrase(reply, CFG, frozenset(CFG["spell_words"])) == phrase


@pytest.mark.parametrize("text, fixed", [
    ("financialy freedom", "financial freedom"),
    ("5k a month", "5k a month"),          # base form of a known word, not a typo
    ("whatever works for me", "whatever works for me"),   # known word plus an ending
    ("time in Dubai!", "time in Dubai!"),
])
def test_fix_typos_keeps_real_words(text, fixed):
    from core.buy_mode.script_engine.words.fill import fix_typos
    vocab = frozenset(CFG["spell_words"]) | {"month", "months", "work"}
    assert fix_typos(text, vocab, CFG) == fixed


def test_the_call_uncovers_the_limiting_belief_and_its_cost_before_the_consequence(fake_embedder):
    s = seller(fake_embedder, step="09")
    s.reply("I'm not smart enough for business")
    assert s.state.step == "belief_origin" and "smart" in s.state.slots["belief"]
    s.reply("my parents always said it")
    assert s.state.step == "belief_cost"
    s.reply("I'd stay stuck and miss my kids growing up")
    assert s.state.step == "10" and "kids" in s.state.slots["belief_cost"]


@pytest.mark.parametrize("said", ["👍", "..."])
def test_a_reply_with_no_words_is_asked_again_never_saved(fake_embedder, said):
    s = seller(fake_embedder, step="03")   # an open step that keeps any reply
    s.reply(said)
    assert s.state.step == "03" and said not in s.state.slots.values()


def test_what_they_meant_is_asked_once_a_step_never_twice(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.reply("More money")
    first, _ = s.reply("Just more money, like")
    second, _ = s.reply("Like more money with stuff right")
    assert "what do you mean" not in first.lower()   # their answer again, only shrug words added
    assert "what do you mean" not in second.lower()


# ---- "who are you" at the very start: a short intro, then a getting-to-know-you question -------------

def test_who_are_you_at_the_start_is_a_short_intro_then_a_question_about_them(fake_embedder):
    s = seller(fake_embedder)
    s.opening()
    text, _ = s.reply("who are you")
    assert text.startswith("We help people build their own business online")
    assert text.endswith(CAT.steps["01"].bridge) and s.state.step == "01" and s.state.bridged


def test_their_reply_to_that_question_is_heard_not_saved_and_the_goal_question_follows(fake_embedder):
    s = seller(fake_embedder)
    s.opening()
    s.reply("who are you")
    text, _ = s.reply("yeah I tried dropshipping")
    assert text == f"{CFG['bridge_ack']} {say('01')}" and s.state.step == "01" and not s.state.bridged
    assert not any(s.state.slots.values())


def test_who_are_you_later_in_the_call_goes_back_to_the_question_without_a_bridge(fake_embedder):
    s = seller(fake_embedder, step="goal_practical", slots={"outcome": "more money"})
    text, _ = s.reply("who are you")
    assert CAT.steps["01"].bridge not in text and not s.state.bridged and "What are you hoping" in text


# ---- replayed calls, round 2 -----------------------------------------------------------------

def test_the_money_question_needs_a_figure(fake_embedder):
    s = seller(fake_embedder, step="02", slots={"outcome": "more money"})
    text, _ = s.reply("I don't know where to start")  # live: taken as their number, and {number} said it later
    assert s.state.step == "02" and "number" not in s.state.slots
    assert text == CAT.steps["02"].probes[0]
    s.reply("about 3k")
    assert s.state.step == "03" and s.state.slots["number"] == "about 3k"


def test_no_figure_after_the_asks_moves_on_unsaved(fake_embedder):
    s = seller(fake_embedder, step="02", slots={"outcome": "more money"})
    for reply in ("financial freedom", "enough to quit", "loads"):
        s.reply(reply)
    assert s.state.step == "03" and "number" not in s.state.slots


def test_a_figure_in_words_is_a_figure(fake_embedder):
    s = seller(fake_embedder, step="02", slots={"outcome": "more money"})
    s.reply("five grand")
    assert s.state.slots["number"] == "five grand"


def test_a_shallow_goal_again_is_not_treated_as_no_answer(fake_embedder):
    s = seller(fake_embedder, step="goal_practical", slots={"outcome": "financial freedom"})
    s.reply("financial freedom")
    text, _ = s.reply("more money")
    assert not any(r in text for r in CAT.reask), text  # "No rush" reads as if they said nothing
    assert text.startswith(CAT.steps["goal_practical"].reask[0])


def test_the_same_fact_twice_gets_a_short_reminder(fake_embedder):
    s = seller(fake_embedder, step="03")
    first, _ = s.reply("what do you do")
    again, _ = s.reply("who are you")
    what = load_offer("shay_coaching").facts["what_we_do"]
    assert what.again and what.again in again and first.split("¶")[0] not in again


def test_a_fact_with_no_reminder_of_its_own_uses_the_shared_one(fake_embedder):
    s = seller(fake_embedder, step="03")
    s.reply("where are you based")
    again, _ = s.reply("where are you based")
    assert again.startswith(SENSE.told_again)


def test_the_price_after_the_pitch_is_said_again_in_full(fake_embedder):
    s = seller(fake_embedder, step="14", told=("price",))
    text, _ = s.reply("how much does it cost")
    assert load_offer("shay_coaching").facts["price"].again not in text


def test_bye_books_the_follow_up(fake_embedder):
    s = seller(fake_embedder, step="04")
    text, _ = s.reply("bye")
    assert s.state.step == CAT.follow_up and text == CAT.steps[CAT.follow_up].say


def test_a_told_fact_survives_a_saved_call(fake_embedder):
    s = seller(fake_embedder, step="03")
    s.reply("where are you based")
    saved = json.loads(json.dumps(s.snapshot()))
    s.restore(saved)
    assert s.state.told == ("location",)


@pytest.mark.parametrize("reply", ["no one knows", "k", "I'd love to take a look"])
def test_words_that_only_look_like_a_figure_are_not_one(fake_embedder, reply):
    s = seller(fake_embedder, step="02", slots={"outcome": "more money"})
    s.reply(reply)
    assert "number" not in s.state.slots


@pytest.mark.parametrize("end", ["later", "end"])
def test_after_the_call_has_ended_every_reply_gets_the_sign_off(fake_embedder, end):
    s = seller(fake_embedder, step=end)
    for reply in ("bye", "ok thanks", "how much was it again?"):
        text, _ = s.reply(reply)  # live: "bye" after the follow-up line said that line again
        assert text == SENSE.ended and s.state.step == end


# ---- replayed calls, round 3 -----------------------------------------------------------------

@pytest.mark.parametrize("reply, kept", [
    ("five grand a month", "five grand a month"),  # live: said at the goal, then asked "how much a month?"
    ("5k a month.", "5k a month"),
    ("five grand a month would change my life", None),  # not only the figure: no want word, not the goal
    ("I make 2k a month", None),
])
def test_a_figure_said_on_its_own_early_answers_the_money_step(reply, kept):
    state = hear_ahead(CAT, ScriptState(step="goal_identity"), reply)
    assert state.slots.get("number") == kept


def test_an_early_figure_skips_the_money_question(fake_embedder):
    s = seller(fake_embedder, step="goal_identity", slots={"outcome": "more money"})
    text, _ = s.reply("five grand a month")
    assert s.state.slots["number"] == "five grand a month" and "each month" not in text


def test_the_money_step_never_says_the_same_line_twice_in_a_row(fake_embedder):
    s = seller(fake_embedder, step="02", slots={"outcome": "more money"})
    texts = [s.reply("not sure")[0] for _ in range(CFG["misses"])]
    assert s.state.step == "02" and texts[0] == CAT.steps["02"].probes[0]
    assert all(not b.endswith(a) for a, b in pairwise(texts))  # live: "If you had to put a number on it..." twice


def test_the_opening_names_the_setter(fake_embedder):
    text, _ = seller(fake_embedder).opening()  # live: {setter} was never filled, so the plain line was said
    assert text.startswith("I believe you had a chat with our setter...")


# ---- side replies in a row never say the same question three times ---------------------------------

def test_a_second_side_question_in_a_row_gets_the_step_in_other_words(fake_embedder):
    s = seller(fake_embedder, step="03")
    first, _ = s.reply("who are you")
    second, _ = s.reply("who are you")
    assert first.endswith(say("03")) and not second.endswith(say("03"))


# ---- a reply that is only a monthly figure answers the number step early ----------------------------

@pytest.mark.parametrize("reply, kept", [
    ("about 5k a month", "5k a month"),
    ("I want 5k a month", "5k a month"),
    ("I make 2k a month", None),
    ("2k a month is what I make", None),
])
def test_a_monthly_figure_said_early_is_kept_only_when_it_is_the_goal(reply, kept):
    state = hear_ahead(CAT, ScriptState(step="goal_identity"), reply)
    assert state.slots.get("number") == kept



# ---- live test calls, round 4 ----------------------------------------------------------------------

def test_what_do_you_mean_is_answered_on_the_step_even_after_its_last_ask(fake_embedder):
    s = seller(fake_embedder, step="01", asks=CFG["misses"])  # live: "hey" used the probe, then "wat do u mean" skipped 01
    s.reply("what do you mean")
    assert s.state.step == "01"


@pytest.mark.parametrize("step, reply", [
    ("goal_practical", "dunno like 10k"),   # live: taken as their practical goal
    ("goal_identity", "a while"),           # live: taken as who they'd be
    ("goal_identity", "like 5 grand"),
    ("03", "nothing"),                      # live: taken as how long they've thought about it
])
def test_a_reply_that_is_no_answer_is_asked_again_not_kept(fake_embedder, step, reply):
    s = seller(fake_embedder, step=step, slots={"outcome": "more money"})
    s.reply(reply)
    assert s.state.step == step and CAT.steps[step].capture not in s.state.slots


@pytest.mark.parametrize("reply, kept", [
    ("like 5 grand", "5 grand"),    # live: a bare figure with no "a month" was not kept for 02
    ("dunno like 10k", "10k"),
    ("I want 10k", None),           # a want with no "a month" may be a lump sum
])
def test_a_bare_big_figure_is_kept_for_the_money_step(reply, kept):
    assert hear_ahead(CAT, ScriptState(step="goal_identity"), reply).slots.get("number") == kept


def test_im_in_is_ready_even_though_it_is_made_of_shrug_words(fake_embedder):
    from dataclasses import replace
    method = replace(CAT, ready=replace(CAT.ready, examples=("yes I'm in",)))
    s = seller(fake_embedder, step="belief_cost", method=method)
    s.reply("yes I'm in")  # live: heard as saying nothing, and asked the cost question again
    assert s.state.step == CAT.ready.then


def test_a_worry_at_the_time_step_is_heard_not_called_a_failed_attempt(fake_embedder):
    from core.buy_mode.script_engine.hear.meanings import load_meanings
    text, _ = seller(fake_embedder, step="03").reply("I'm scared of losing money")
    assert text.startswith(load_meanings().items["fear_of_loss"].lines[0]) and "Sorry to hear" not in text


def test_a_price_request_gets_the_price_answer_and_keeps_the_step(fake_embedder):
    s = seller(fake_embedder, step="04")
    s.reply("my partner would have to be on board")
    text, _ = s.reply("can you just tell me the price")  # live: "I haven't mentioned a price yet", then 04 skipped
    assert text.startswith(load_offer("shay_coaching").facts["price"].answer) and s.state.step == "04"


def test_a_money_goal_is_not_said_back_in_the_money_question(fake_embedder):
    s = seller(fake_embedder, step="goal_identity", slots={"outcome": "make more money"})
    text, _ = s.reply("I want to finally be proud of myself")  # live: "each month to make more money?"
    assert text.endswith(CAT.steps["02"].say_plain)


def test_a_side_reply_that_moves_the_step_shows_the_new_stage(fake_embedder):
    s = seller(fake_embedder, step="12")
    s.reply("who are you")
    _, stage = s.reply("who are you")  # the second side reply in a row moves 12 (no other words) on to 13
    assert s.state.step == "13" and stage == CAT.steps["13"].ui_stage != CAT.steps["12"].ui_stage


@pytest.mark.parametrize("said, step", [
    ("dunno, a year?", "04"),          # live: "I'll find out and let you know": the answer said with a rise
    ("how long will it take?", "03"),  # a real question with a span-of-time word still asks
])
def test_a_short_answer_with_a_question_mark_is_still_the_answer(fake_embedder, said, step):
    s = seller(fake_embedder, step="03")
    s.reply(said)
    assert s.state.step == step


def test_a_yes_or_no_question_asked_again_never_asks_for_a_rough_idea(fake_embedder):
    s = seller(fake_embedder, step="m_close2")   # live: "No rush, even a rough idea helps. Do you see yourself jumping in?"
    reply, _ = s.reply("banana")
    assert reply.startswith("No pressure either way.") and s.state.step == "m_close2"
