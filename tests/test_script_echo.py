"""The echo budget (echo.py), the meaning bank (meanings.yaml) and tone marks (tone.py): their words said
back at the moments, a short term at most elsewhere, never in two messages in a row; else what they meant;
else nothing. Offline: bag-of-words embedder. The real model's reading of each meaning is at the end (opt-in)."""
import json
import os
from pathlib import Path

import pytest

from core.loader import load_yaml
from core.script_engine.echo import Echo
from core.script_engine.engine import ScriptState
from core.script_engine.method import (
    load_common_sense,
    load_meanings,
    load_method,
    load_offer,
    parse_meanings,
    parse_method,
)
from core.script_engine.recognise import Listener
from core.script_engine.seller import ScriptSeller
from core.script_engine.tone import join, plain, stresses

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")
MEANINGS = load_meanings()


class Mirror:
    """A fake AI whose "I heard you" line says their reply back, as the AI is told to. Counts the ack calls."""

    def __init__(self):
        self.acks = 0

    def __call__(self, prompt, max_tokens):
        reply = prompt.split("<reply>")[1].split("</reply>")[0].strip() if "<reply>" in prompt else ""
        if "<goal>" in prompt:  # the listen call
            return f"ANSWERED: yes\nACK: So, {reply}.\nPROBE: none"
        if "They answered" in prompt:  # the ack call
            self.acks += 1
            return f"So, {reply}."
        raise RuntimeError("only the ack and listen calls are faked")


def seller(bow, llm=None, step=None, meanings=MEANINGS, **state):
    s = ScriptSeller(CFG, CAT, load_offer("shay_coaching"), load_common_sense(), bow, llm or Mirror(), meanings)
    if step:
        s.reset(ScriptState(step=step, **state))
    return s


NO_MEANINGS = parse_meanings({"min_score": 1.0, "meanings": {}})


# ---- the budget -------------------------------------------------------------------------------

CALL = ["more money", "paying the bills", "someone my kids look up to", "5k a month", "2 years",
        "paying the bills", "two jobs", "videos on youtube"]


def test_no_two_messages_in_a_row_say_their_words_back_outside_a_moment(fake_embedder):
    s = seller(fake_embedder, meanings=NO_MEANINGS)
    s.opening()
    last = False
    for reply in CALL:
        s.reply(reply)
        moment = CAT.steps[s.state.step].moment
        assert not (last and s.state.quoted and not moment), (reply, s.state.step)
        last = s.state.quoted


def test_the_goal_question_says_their_words_even_right_after_a_quote(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.state = Echo.settle(s.state, Echo.new_turn(s.state))
    from dataclasses import replace
    s.reset(replace(s.state, quoted=True))
    text, _ = s.reply("more money")
    assert text == "What are you hoping to achieve with more money?"
    assert s.state.quoted


def test_the_same_phrase_comes_back_at_most_twice_a_call(fake_embedder):
    s = seller(fake_embedder, meanings=NO_MEANINGS, step="01")
    said = [s.reply(r)[0] for r in ["more money", "paying the bills", "someone my kids look up to",
                                    "5k a month", "2 years", "because it eats me up", "no time", "nothing"]]
    assert sum("more money" in t for t in said) <= 1 + CFG["echo_repeats"]  # the moment, then the budget
    assert sum("more money" in t for t in said[1:]) <= CFG["echo_repeats"]


def test_a_long_phrase_of_theirs_waits_for_a_moment(fake_embedder):
    s = seller(fake_embedder)
    s.reset(ScriptState(step="05", slots={"outcome": "I want to be my own boss"}))
    text, _ = s.reply("no time")
    assert "own boss" not in text and text.endswith(CAT.steps["06"].say_plain)


def test_one_quote_per_message(fake_embedder):
    # 05's line names their goal, so the AI's line (which would say "no time" back) is not asked for
    ai = Mirror()
    s = seller(fake_embedder, ai, meanings=NO_MEANINGS, step="05", slots={"outcome": "more money"})
    text, _ = s.reply("no time")
    assert text == "What are you doing now to get more money rather than just dream about it?"
    assert ai.acks == 0


def test_the_ai_line_is_not_asked_for_when_the_last_message_quoted_them(fake_embedder):
    ai = Mirror()
    s = seller(fake_embedder, ai, meanings=NO_MEANINGS, step="01")
    s.reply("more money")                       # the goal question says "more money"
    text, _ = s.reply("paying the bills")       # level 2: on to the identity question
    assert text == CAT.steps["goal_identity"].say and ai.acks == 0
    text, _ = s.reply("someone my kids look up to")  # 02's own line names their goal: that is this message's quote
    assert text == "How much would you need to be making each month to have more money?" and ai.acks == 0


def test_the_ai_line_is_asked_for_when_the_budget_allows(fake_embedder):
    ai = Mirror()
    s = seller(fake_embedder, ai, meanings=NO_MEANINGS, step="04")
    text, _ = s.reply("because it eats me up")
    assert text.startswith("So, because it eats me up.") and s.state.quoted  # the listen call's line
    text, _ = s.reply("I tried a course and it flopped")  # the next message may not say their words back
    assert "course" not in text and not s.state.quoted


def test_an_ai_line_saying_a_whole_sentence_back_is_dropped(fake_embedder):
    s = seller(fake_embedder, Mirror(), meanings=NO_MEANINGS, step="04")
    text, _ = s.reply("because I hate my boss and my commute every single day")
    assert not text.startswith("So,") and not s.state.quoted


def test_a_line_already_in_their_words_counts_as_a_quote(fake_embedder):
    # "What do you mean by wanting to make money online?" comes filled in: it still uses up the quote
    s = seller(fake_embedder, meanings=NO_MEANINGS)
    s.opening()
    text, _ = s.reply("I want to make money online")
    assert "make money online" in text and s.state.quoted and s.state.echoed


def test_quotes_reads_their_words_in_a_line():
    echo = Echo(CFG, NO_MEANINGS, Listener(CFG, None))
    assert echo.quotes("Okay, money, that makes sense.", "money")
    assert echo.quotes("So paying the bills is the big one.", "pay my bills I guess") is False  # one of two words
    assert echo.quotes("So the bills are the big one.", "the bills, honestly")
    assert not echo.quotes("That makes sense.", "my mum's relying on me")
    assert not echo.quotes("Got it.", "ok")  # nothing in "ok" to quote


def test_the_budget_survives_a_rewind(fake_embedder):
    s = seller(fake_embedder, step="01")
    s.reply("more money")
    saved = json.loads(json.dumps(s.snapshot()))  # as the session store keeps it
    t = seller(fake_embedder)
    t.restore(saved)
    assert t.state == s.state and isinstance(t.state.echoed, tuple) and isinstance(t.state.meant, tuple)


# ---- the meaning bank -------------------------------------------------------------------------


def test_a_meaning_line_is_said_in_its_own_bubble_before_the_question(fake_embedder):
    ai = Mirror()
    s = seller(fake_embedder, ai, step="04")
    text, _ = s.reply("my mum's relying on me")
    first = MEANINGS.items["family_duty"].lines[0]
    assert text.startswith(first + "¶") and ai.acks == 0  # no AI line when a meaning says it
    assert first in s.state.meant and not s.state.quoted


def test_each_meaning_line_is_said_once_a_call_in_turn(fake_embedder):
    lines = MEANINGS.items["family_duty"].lines
    s = seller(fake_embedder, step="04")
    first, _ = s.reply("my mum's relying on me")
    s.reset(ScriptState(step="04", meant=s.state.meant))
    second, _ = s.reply("my mam needs me")
    s.reset(ScriptState(step="04", meant=s.state.meant))
    third, _ = s.reply("my family is counting on me")
    assert first.startswith(lines[0]) and second.startswith(lines[1])
    assert not any(line in third for line in lines)  # all said: nothing, or the AI's line


def test_a_step_line_of_its_own_still_wins(fake_embedder):
    # 03's own "24 months... Damn." is the reaction: no meaning line on top of it
    s = seller(fake_embedder, step="03")
    text, _ = s.reply("2 years")
    assert text.startswith("24 months... Damn.¶") and not s.state.meant


def test_meaning_lines_never_ask_and_stress_once_at_most():
    for m in MEANINGS.items.values():
        for line in m.lines:
            assert "?" not in line and stresses(line) <= 1


@pytest.mark.parametrize("bad, why", [
    ({"meanings": {"x": {"examples": ["a"], "lines": ["ok?"]}}, "min_score": 0.8}, "neither asks"),
    ({"meanings": {"x": {"examples": ["a"], "lines": ["==so== _very_ much"]}}, "min_score": 0.8}, "one stress"),
    ({"meanings": {"x": {"examples": ["a"], "lines": ["for {outcome}"]}}, "min_score": 0.8}, "blanks"),
    ({"meanings": {"x": {"lines": ["ok"]}}, "min_score": 0.8}, "needs examples"),
    ({"meanings": {}}, "min_score"),
])
def test_a_broken_meaning_bank_fails_loud(bad, why):
    with pytest.raises(ValueError, match=why):
        parse_meanings(bad)


# ---- the script's own checks ------------------------------------------------------------------

def _method(**step):
    base = {"ui_stage": "intent", "say": "Go?", "listen": {"any": {"then": "b"}}}
    return {"first": "a", "price_step": "b", "steps": {
        "a": {**base, "capture": "outcome", "echo": True},
        "b": {**base, **step},
    }}


@pytest.mark.parametrize("step, why", [
    ({"say": "So {outcome}?"}, "needs a say_plain"),
    ({"say": "Go?", "probe": ["And {outcome}?"], "stuck": {"then": "a"}}, "probes never say"),
    ({"say": "It's _all_ about ==you==?"}, "one stress"),
    ({"say": "Go?", "listen": {"any": {"then": "a", "min_score": 0.5}}}, "no min_score"),
])
def test_a_line_the_budget_could_not_handle_fails_loud(step, why):
    with pytest.raises(ValueError, match=why):
        parse_method("t", _method(**step))


def test_every_script_loads_with_its_lines_checked():
    for name in ("cat", "impact_formula"):
        load_method(name)
    load_common_sense()
    assert MEANINGS.items


# ---- tone marks -------------------------------------------------------------------------------


def test_plain_drops_the_marks():
    assert plain("So it's about ==them==.¶Taking over _all_ the bills…") == "So it's about them. Taking over all the bills…"
    assert plain("It's _yours_: (all _of_ it) — “_now_”") == "It's yours: (all of it) — “now”"
    assert plain("it is _all_-in") == "it is all-in" and stresses("it is _all_-in") == 1
    assert plain("the belief_cost slot") == "the belief_cost slot"  # an underscore inside a word is no stress


def test_stresses_counts_both_marks():
    assert stresses("It's _all_ on ==you==") == 2
    assert stresses("belief_cost and ==you==") == 1


def test_join_puts_each_part_in_its_own_bubble():
    assert join("I'm sorry.", "", " Why? ") == "I'm sorry.¶Why?"
    assert join("Damn.¶", "What?") == "Damn.¶What?"  # never an empty bubble


def test_the_ai_reads_the_question_without_marks(fake_embedder):
    prompts = []

    def ai(prompt, n):
        prompts.append(prompt)
        raise RuntimeError("down")

    s = seller(fake_embedder, ai, step="04", meanings=NO_MEANINGS)
    s.reply("because it eats me up")
    assert prompts and all("¶" not in p and "==" not in p for p in prompts)


# ---- the real model (opt-in) ------------------------------------------------------------------

real = pytest.mark.skipif(os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)")


@pytest.fixture(scope="module")
def model():
    from core.script_engine.embedder import make_embedder
    return make_embedder(CFG, Path(__file__).parent.parent)


def _down(prompt, n):
    raise RuntimeError("AI off")


@real
@pytest.mark.parametrize("reply", ["my mam needs me", "my mum's relying on me"])
def test_two_ways_of_saying_family_get_the_same_line(model, reply):
    text, _ = seller(model, _down, step="04").reply(reply)
    assert text.startswith(MEANINGS.items["family_duty"].lines[0] + "¶")


@real
def test_a_hard_time_is_met_with_sorry_not_the_failed_attempt_line(model):
    text, _ = seller(model, _down, step="03").reply(
        "since my dad got sick last year. I had to take over all the bills, it's been really hard")
    assert "first attempt" not in text
    assert text.startswith(MEANINGS.items["health_event"].lines[0] + "¶")


@real
@pytest.mark.parametrize("reply", ["since my mum got ill", "since my dad got sick a while back"])
def test_the_judge_never_picks_a_route_under_its_floor(model, reply):
    def judge_says_failed(prompt, n):
        if "failed_before" in prompt:
            return "failed_before"
        raise RuntimeError("AI off")
    text, _ = seller(model, judge_says_failed, step="03").reply(reply)
    assert "first attempt" not in text


@real
@pytest.mark.parametrize("reply", ["I tried a course and it flopped", "I tried dropshipping and it failed"])
def test_a_real_failed_attempt_still_gets_its_line(model, reply):
    text, _ = seller(model, _down, step="03").reply(reply)
    assert "first attempt" in text


@real
@pytest.mark.parametrize("reply", ["2 years", "about 2 years", "a few years", "6 months"])
def test_time_answers_still_get_the_months_line_or_the_question(model, reply):
    text, _ = seller(model, _down, step="03").reply(reply)
    assert "first attempt" not in text and not any(line in text for m in MEANINGS.items.values() for line in m.lines)


@real
@pytest.mark.parametrize("reply", ["5k a month", "about two years", "I watch youtube videos", "more money",
                                   "nothing really", "risk taking", "I want to be someone my kids look up to",
                                   "for my mum", "for my kids", "my job", "I work full time", "debt", "the bills",
                                   "my family", "bills", "because of my kids"])
def test_everyday_answers_mean_nothing_in_the_bank(model, reply):
    listener = Listener(CFG, model)
    echo = Echo(CFG, MEANINGS, listener)
    assert echo.meaning(reply, ScriptState(step="04"), Echo.new_turn(ScriptState(step="04"))) == ""
