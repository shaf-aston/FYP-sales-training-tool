"""The meaning bank (meanings.py): a prewritten line for what they meant, in its own bubble, each once a
call. Offline: bag-of-words embedder. The real model's reading of each meaning is at the end (opt-in)."""
import os
from pathlib import Path

import pytest

from core.loader import load_yaml
from core.script_engine.meanings import MeaningBank, load_meanings, parse_meanings
from core.script_engine.recognise import Listener
from core.script_engine.tone import stresses

CFG = load_yaml("script/engine.yaml")
MEANINGS = load_meanings()


def test_a_meaning_line_is_said_in_its_own_bubble_before_the_question(fake_embedder, cat_seller, mirror):
    s = cat_seller(fake_embedder, mirror, step="04")
    text, _ = s.reply("my mum's relying on me")
    first = MEANINGS.items["family_duty"].lines[0]
    assert text.startswith(first + "¶") and mirror.acks == 0  # no AI line when a meaning says it
    assert first in s.state.meant and not s.state.quoted


def test_each_meaning_line_is_said_once_a_call_in_turn(fake_embedder, cat_seller):
    lines = MEANINGS.items["family_duty"].lines
    s = cat_seller(fake_embedder, step="04")
    first, _ = s.reply("my mum's relying on me")
    s = cat_seller(fake_embedder, step="04", meant=s.state.meant)
    second, _ = s.reply("my mam needs me")
    s = cat_seller(fake_embedder, step="04", meant=s.state.meant)
    third, _ = s.reply("my family is counting on me")
    assert first.startswith(lines[0]) and second.startswith(lines[1])
    assert not any(line in third for line in lines)  # all said: nothing, or the AI's line


def test_a_step_line_of_its_own_still_wins(fake_embedder, cat_seller):
    # 03's own "24 months... Damn." is the reaction: no meaning line on top of it
    s = cat_seller(fake_embedder, step="03")
    text, _ = s.reply("2 years")
    assert text.startswith("24 months... Damn.¶") and not s.state.meant


def test_meaning_lines_never_ask_and_stress_once_at_most():
    assert MEANINGS.items
    for m in MEANINGS.items.values():
        for line in m.lines:
            assert "?" not in line and stresses(line) <= 1


@pytest.mark.parametrize("bad, why", [
    ({"meanings": {"x": {"examples": ["a"], "lines": ["ok?"]}}, "min_score": 0.8}, "neither asks"),
    ({"meanings": {"x": {"examples": ["a"], "lines": ["==so== _very_ much"]}}, "min_score": 0.8}, "one stress"),
    ({"meanings": {"x": {"examples": ["a"], "lines": ["for {outcome}"]}}, "min_score": 0.8}, "blanks"),
    ({"meanings": {"x": {"lines": ["ok"]}}, "min_score": 0.8}, "needs examples"),
    ({"meanings": {}}, "min_score"),
    ({"meanings": {}, "min_score": 0.8, "min_words": True}, "whole number"),
])
def test_a_broken_meaning_bank_fails_loud(bad, why):
    with pytest.raises(ValueError, match=why):
        parse_meanings(bad)


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
def test_two_ways_of_saying_family_get_the_same_line(model, cat_seller, reply):
    text, _ = cat_seller(model, _down, step="04").reply(reply)
    assert text.startswith(MEANINGS.items["family_duty"].lines[0] + "¶")


@real
def test_a_hard_time_is_met_with_sorry_not_the_failed_attempt_line(model, cat_seller):
    text, _ = cat_seller(model, _down, step="03").reply(
        "since my dad got sick last year. I had to take over all the bills, it's been really hard")
    assert "first attempt" not in text
    assert text.startswith(MEANINGS.items["health_event"].lines[0] + "¶")


@real
@pytest.mark.parametrize("reply", ["since my mum got ill", "since my dad got sick a while back"])
def test_the_judge_never_picks_a_route_under_its_floor(model, cat_seller, reply):
    def judge_says_failed(prompt, n):
        if "failed_before" in prompt:
            return "failed_before"
        raise RuntimeError("AI off")
    text, _ = cat_seller(model, judge_says_failed, step="03").reply(reply)
    assert "first attempt" not in text


@real
@pytest.mark.parametrize("reply", ["I tried a course and it flopped", "I tried dropshipping and it failed"])
def test_a_real_failed_attempt_still_gets_its_line(model, cat_seller, reply):
    text, _ = cat_seller(model, _down, step="03").reply(reply)
    assert "first attempt" in text


@real
@pytest.mark.parametrize("reply", ["2 years", "about 2 years", "a few years", "6 months"])
def test_time_answers_still_get_the_months_line_or_the_question(model, cat_seller, reply):
    text, _ = cat_seller(model, _down, step="03").reply(reply)
    assert "first attempt" not in text and not any(line in text for m in MEANINGS.items.values() for line in m.lines)


@real
@pytest.mark.parametrize("reply", ["5k a month", "about two years", "I watch youtube videos", "more money",
                                   "nothing really", "risk taking", "I want to be someone my kids look up to",
                                   "for my mum", "for my kids", "my job", "I work full time", "debt", "the bills",
                                   "my family", "bills", "because of my kids"])
def test_everyday_answers_mean_nothing_in_the_bank(model, reply):
    assert MeaningBank(CFG, MEANINGS, Listener(CFG, model)).line(reply, ()) == ""
