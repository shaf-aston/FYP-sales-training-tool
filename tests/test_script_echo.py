"""The echo budget (echo.py): their words said back at the moments, a short term at most elsewhere, never in
two messages in a row. Offline: bag-of-words embedder, and a fake AI that says their reply back."""
import json

import pytest

from core.infra.loader import load_yaml
from core.buy_mode.script_engine.words.echo import Echo
from core.buy_mode.script_engine.hear.meanings import parse_meanings
from core.buy_mode.script_engine.method import load_common_sense, load_method, parse_method

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")
NO_MEANINGS = parse_meanings({"min_score": 1.0, "meanings": {}})

CALL = ["more money", "paying the bills", "someone my kids look up to", "5k a month", "2 years",
        "paying the bills", "two jobs", "videos on youtube"]


def test_no_two_messages_in_a_row_say_their_words_back_outside_a_moment(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS)
    s.opening()
    last = False
    for reply in CALL:
        s.reply(reply)
        moment = CAT.steps[s.state.step].moment
        assert not (last and s.state.quoted and not moment), (reply, s.state.step)
        last = s.state.quoted


def test_the_goal_question_says_their_words_even_right_after_a_quote(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, step="01", quoted=True)
    text, _ = s.reply("more money")
    assert text == "What are you hoping to achieve with more money?"
    assert s.state.quoted


def test_the_same_phrase_comes_back_at_most_twice_a_call(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS, step="01")
    said = [s.reply(r)[0] for r in ["more money", "paying the bills", "someone my kids look up to",
                                    "5k a month", "2 years", "because it eats me up", "no time", "nothing"]]
    assert sum("more money" in t for t in said[1:]) <= CFG["echo_repeats"]  # after the moment, the budget


def test_a_long_phrase_of_theirs_waits_for_a_moment(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, step="05", slots={"outcome": "I want to be my own boss"})
    text, _ = s.reply("no time")
    assert "own boss" not in text and text.endswith(CAT.steps["06"].say_plain)


def test_one_quote_per_message(fake_embedder, cat_seller, mirror):
    # 05's line names their goal, so the AI's line (which would say "no time" back) is not asked for
    s = cat_seller(fake_embedder, mirror, meanings=NO_MEANINGS, step="05", slots={"outcome": "more money"})
    text, _ = s.reply("no time")
    assert text == "What are you doing now to get more money rather than just dream about it?"
    assert mirror.acks == 0


def test_the_ai_line_is_not_asked_for_when_the_last_message_quoted_them(fake_embedder, cat_seller, mirror):
    s = cat_seller(fake_embedder, mirror, meanings=NO_MEANINGS, step="01")
    s.reply("financial freedom")                # the goal question says "financial freedom"
    text, _ = s.reply("paying the bills")       # level 2: on to the identity question
    assert text == CAT.steps["goal_identity"].say and mirror.acks == 0
    text, _ = s.reply("someone my kids look up to")  # 02's own line names their goal: that is this message's quote
    assert text == "How much would you need to be making each month to have financial freedom?" and mirror.acks == 0


def test_the_ai_line_is_asked_for_when_the_budget_allows(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS, step="04")
    text, _ = s.reply("because it eats me up")
    assert text.startswith("So, because it eats me up.") and s.state.quoted  # the listen call's line
    text, _ = s.reply("I tried a course and it flopped")  # the next message may not say their words back
    assert "course" not in text and not s.state.quoted


def test_an_ai_line_never_says_a_phrase_back_past_its_cap(fake_embedder, cat_seller):
    # the AI line quotes "because eats up", the filled blank "because it eats me up": the same phrase
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS, step="04", echoed=("because it eats me up",) * 2)
    text, _ = s.reply("because it eats me up")
    assert not text.startswith("So,") and not s.state.quoted


def test_the_scripts_own_question_asked_again_is_not_a_quote(fake_embedder, cat_seller):
    # 08 has no probes: asked again, its question comes back without the talk before it. Those words are the
    # script's, even where they share some with the reply, so the next message may still quote them.
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS, step="08")
    text, _ = s.reply("what do you mean by business owner employee")
    assert text.endswith("What's the main difference between a successful business owner and an employee?")
    assert not s.state.quoted and s.state.echoed == ()


def test_an_ai_line_saying_a_whole_sentence_back_is_dropped(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS, step="04")
    text, _ = s.reply("because I hate my boss and my commute every single day")
    assert not text.startswith("So,") and not s.state.quoted


def test_a_line_already_in_their_words_counts_as_a_quote(fake_embedder, cat_seller):
    # "What do you mean by wanting to make money online?" comes filled in: it still uses up the quote
    s = cat_seller(fake_embedder, meanings=NO_MEANINGS)
    s.opening()
    text, _ = s.reply("I want to make money online")
    assert "make money online" in text and s.state.quoted and s.state.echoed


def test_quoted_reads_their_words_in_a_line():
    echo = Echo(CFG)
    assert echo.quoted("Okay, money, that makes sense.", "money") == ["money"]
    assert echo.quoted("So paying the bills is the big one.", "pay my bills I guess") == []  # one of two words
    assert echo.quoted("So the bills are the big one.", "the bills, honestly")
    assert echo.quoted("That makes sense.", "my mum's relying on me") == []
    assert echo.quoted("Got it.", "ok") == []  # nothing in "ok" to quote


def test_the_budget_survives_a_rewind(fake_embedder, cat_seller):
    s = cat_seller(fake_embedder, step="01")
    s.reply("more money")
    saved = json.loads(json.dumps(s.snapshot()))  # as the session store keeps it
    t = cat_seller(fake_embedder)
    t.restore(saved)
    assert t.state == s.state and isinstance(t.state.echoed, tuple) and isinstance(t.state.meant, tuple)


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
    ({"say": "So {outcome }?", "say_plain": "So?"}, "a blank is"),
    ({"say": "Go?", "listen": {"any": {"then": "a", "min_score": 0.5}}}, "no min_score"),
])
def test_a_line_the_budget_could_not_handle_fails_loud(step, why):
    with pytest.raises(ValueError, match=why):
        parse_method("t", _method(**step))


def test_every_script_loads_with_its_lines_checked():
    for name in ("cat", "impact_formula"):
        load_method(name)
    load_common_sense()
