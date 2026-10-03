"""Slice 4: AI gap rules (checks, fill, judge) and the trainer's rules (R5), offline."""
import json
import logging
import re

import pytest

from core.loader import load_yaml
from core.script_engine.checks import CheckContext, check
from core.script_engine.engine import ScriptState
from core.script_engine.fill import fill_step, offer_blanks
from core.script_engine.judge import VAGUE, judge
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.seller import ScriptSeller

CFG = load_yaml("selling.yaml")
OFFER = load_offer("shay_coaching")


def ctx(**kw):
    base = {"max_words": 30, "questions": 1, "price_ok": False, "price": "$5k"}
    return CheckContext(**{**base, **kw})


# ---- checks: one test per rule ------------------------------------------------------------

@pytest.mark.parametrize("text, kw, rule", [
    ("Why? Really?", {}, "question_count"),
    ("Nice point.", {}, "question_count"),
    ("It is fine but what next?", {}, "says_but"),
    ("What did you mean when you said that?", {}, "says_you_said"),
    ("Any questions?", {}, "any_questions"),
    ("It is $5k, ready?", {}, "early_price"),
    ("It costs 5k, ready?", {"price": "5k"}, "early_price"),
    ("Hi {name}, ready?", {}, "unfilled_blank"),
    ("one two three four?", {"max_words": 3}, "length"),
    ("freedom and yachts", {"questions": 0, "prospect_words": frozenset({"freedom"})},
     "not_prospect_words"),
])
def test_each_rule_fires(text, kw, rule):
    assert rule in check(text, ctx(**kw))


def test_clean_sentences_pass():
    assert check("What would change for you?", ctx()) == []
    assert check("It is $5k, ready?", ctx(price_ok=True)) == []
    allowed = ctx(questions=0, prospect_words=frozenset({"freedom"}), stop_words=frozenset({"and"}))
    assert check("freedom and freedom", allowed) == []


# ---- fill ---------------------------------------------------------------------------------

STEP_SAY = "How much do you need to be making to feel {outcome} freedom?"
STEP_PLAIN = "How much do you need to be making to feel that freedom?"


def _fill(llm, slots=None):
    slots = {"outcome": "I want financial freedom"} if slots is None else slots
    return fill_step(STEP_SAY, "", STEP_PLAIN, slots, OFFER, CFG, llm)


def test_fill_uses_a_phrase_from_the_prospect():
    assert _fill(lambda p, n: "financial") == "How much do you need to be making to feel financial freedom?"


def test_fill_retries_once_then_uses_plain_line(caplog):
    calls = []

    def llm(prompt, n):
        calls.append(prompt)
        return "luxury yachts"  # words the prospect never said

    with caplog.at_level(logging.WARNING, logger="script_engine.fallback"):
        assert _fill(llm) == STEP_PLAIN
    assert len(calls) == 1 + CFG["ai_retries"]
    assert "fallback to plain line" in caplog.text


def test_fill_survives_ai_errors_and_missing_slots():
    def down(prompt, n):
        raise RuntimeError("provider down")

    assert _fill(down) == STEP_PLAIN
    assert _fill(lambda p, n: "financial", slots={}) == STEP_PLAIN


def test_fill_offer_blanks_need_no_ai():
    def never(prompt, n):
        raise AssertionError("AI must not be called")

    line = fill_step("{months}-month process, investment is {price}.", "", "", {}, OFFER, CFG, never)
    assert line == "6-month process, investment is $5k."


def test_ack_with_blank_is_dropped_when_it_cannot_be_filled():
    out = fill_step("Next?", "for {years} years.", "", {}, OFFER, CFG, lambda p, n: "x")
    assert out == "Next?"


# ---- judge --------------------------------------------------------------------------------

CANDS = {"agrees": ["yes"], "unclear": ["I am lost"]}


def test_judge_picks_a_candidate_or_vague():
    assert judge("hm", CANDS, lambda p, n: "Agrees.") == "agrees"
    assert judge("hm", CANDS, lambda p, n: "no idea") == VAGUE
    assert judge("hm", CANDS, lambda p, n: "vague") == VAGUE


def test_judge_ai_down_counts_as_vague():
    def down(prompt, n):
        raise RuntimeError("down")

    assert judge("hm", CANDS, down) == VAGUE


# ---- seller: the trainer's rules (R5) -----------------------------------------------------

class Vectors:
    """Embedder that maps a text to a chosen vector; unknown texts get an orthogonal one."""

    def __init__(self, table=None):
        self.table = table or {}

    def embed(self, texts):
        return [self.table.get(t, [0.0, 0.0, 1.0]) for t in texts]


def fake_llm(prompt, max_tokens):
    """Fills blanks with the prospect's first word; answers a product question in one line."""
    if "Fill the blank" in prompt:
        return prompt.split("Prospect said:")[1].split()[0]
    if "A prospect asked" in prompt:
        return "Yes, we have a clear process for that."
    return "vague"


def make_seller(bow, llm=fake_llm, method="cat"):
    cfg = {**CFG, "threshold": 0.5}
    return ScriptSeller(cfg, load_method(method), OFFER, load_common_sense(), bow, llm)


@pytest.fixture
def seller(fake_embedder):
    return make_seller(fake_embedder)


def at(seller, step, **slots):
    seller.reset(ScriptState(step=step, slots=slots, last_point=slots.get("why", "")))
    return seller


def test_price_early_gets_one_line_then_first_questions(seller):
    text, _ = at(seller, "03", outcome="I want financial freedom").reply("how much does it cost")
    assert "first a couple of questions" in text
    assert "$5k" not in text
    assert text.endswith("How long have you been thinking about this?")
    assert seller.state.step == "03"


def test_what_do_you_do_early_gets_one_line_then_first_questions(seller):
    text, _ = at(seller, "03").reply("what do you do")
    assert "First, a couple of questions" in text
    assert text.endswith("How long have you been thinking about this?")


def test_price_after_price_step_is_stated(seller):
    text, _ = at(seller, "18").reply("how much does it cost")
    assert "$5k" in text and "6-month" in text


@pytest.mark.parametrize("name, said, lines", [
    ("money", "it's too expensive", ["How much do you have now?"]),
    ("think", "I need to think about it", ["How long have you been researching?"]),
])
def test_objection_loops_twice_then_direct_then_follow_up(seller, name, said, lines):
    method = seller.method
    at(seller, "19")
    said_lines = [seller.reply(said)[0] for _ in range(4)]
    objection = method.objections[name]
    assert said_lines[0] == objection.loop[0]
    assert said_lines[1] == objection.loop[1]
    assert said_lines[2] == objection.direct
    assert said_lines[3] == method.follow_up
    assert lines[0] in said_lines[0]


def test_objections_are_counted_separately(seller):
    at(seller, "19")
    seller.reply("it's too expensive")
    first_think = seller.reply("I need to think about it")[0]
    assert first_think == seller.method.objections["think"].loop[0]


def test_nothing_in_the_scripts_asks_any_questions():
    for name in ("cat", "impact_formula"):
        text = json.dumps(load_method(name), default=lambda o: o.__dict__).lower()
        assert "any questions" not in text


def test_a_whole_opening_run_has_no_any_questions_or_open_blanks(seller):
    seller.reset()
    prospect = ["I want financial freedom", "ten thousand a month", "about three years",
                "it keeps me up", "no time", "not much", "I do not know"]
    said = [seller.opening()[0]] + [seller.reply(r)[0] for r in prospect]
    for line in said:
        assert "any questions" not in line.lower()
        assert line.count("?") <= 1, line
        assert "{" not in line


def test_uncovered_product_question_is_answered_logged_then_back_to_script(seller, caplog):
    at(seller, "03", why="more time with my kids")
    with caplog.at_level(logging.INFO, logger="script_engine.uncovered"):
        text, _ = seller.reply("will refunds exist?")
    assert text.startswith("Yes, we have a clear process for that.")
    assert text.endswith("how long have you been thinking about this?")
    assert "So, as you mentioned" in text
    assert json.loads(caplog.records[0].message)["question"] == "will refunds exist?"
    assert seller.state.step == "03"


def test_uncovered_question_with_a_rule_breaking_answer_is_dropped(seller, caplog):
    def pushy(prompt, n):
        return "It is $5k but worth it." if "A prospect asked" in prompt else fake_llm(prompt, n)

    s = at(make_seller(seller._embedder, pushy), "03")
    with caplog.at_level(logging.WARNING, logger="script_engine.fallback"):
        text, _ = s.reply("will refunds exist?")
    assert text == "How long have you been thinking about this?"
    assert "broke" in caplog.text


def test_ai_down_never_blocks_a_turn(seller):
    def down(prompt, n):
        raise RuntimeError("down")

    s = at(make_seller(seller._embedder, down), "03", outcome="I want financial freedom")
    text, _ = s.reply("will refunds exist?")
    assert text == "How long have you been thinking about this?"
    text, _ = at(s, "02", outcome="I want financial freedom").reply("ten thousand")
    assert text == "How long have you been thinking about this?"
    text, _ = at(s, "05", outcome="I want financial freedom").reply("no time")
    assert "that" in text and "{" not in text    # say_plain used for step 06


def test_common_sense_interruption_then_bring_back(seller):
    text, stage = at(seller, "03", why="more time with my kids").reply("hold on a second")
    assert text.startswith("No problem, take your time.")
    assert text.endswith("how long have you been thinking about this?")
    assert stage == "logical" and seller.state.step == "03"


def _close_call_seller(llm):
    bow = Vectors()
    cat = load_method("cat")
    for route in cat.steps["18"].listen:
        for example in route.examples:
            bow.table[example] = [0.8, 0.6 if route.signal == "agrees" else -0.6, 0.0]
    bow.table["hmm"] = [1.0, 0.0, 0.0]
    return make_seller(bow, llm)


def test_close_call_goes_to_the_judge(seller):
    s = at(_close_call_seller(lambda p, n: "agrees"), "18")
    s.reply("hmm")
    assert s.state.step == "19"


def test_close_call_with_ai_down_probes_instead(seller):
    def down(prompt, n):
        raise RuntimeError("down")

    s = at(_close_call_seller(down), "18")
    text, _ = s.reply("hmm")
    assert s.state.step == "18"
    assert text == "That's everything in a nutshell. Does that make sense?"


def test_replay_gives_the_same_lines(fake_embedder):
    replies = ["I want to be free from my 9-5 and work from anywhere", "ten thousand", "3 years"]

    def run():
        s = make_seller(fake_embedder)
        return [s.opening()[0]] + [s.reply(r)[0] for r in replies]

    assert run() == run()


def test_observe_rebuilds_state_without_ai(fake_embedder):
    live = make_seller(fake_embedder)
    replay = make_seller(fake_embedder, llm=None)
    for reply in ["I want financial freedom", "ten thousand", "3 years"]:
        live.reply(reply)
        replay.observe(reply)
    assert replay.state == live.state


@pytest.mark.parametrize("method", ["cat", "impact_formula"])
def test_every_prospect_blank_has_a_plain_line(method):
    known = set(offer_blanks(OFFER))
    for step in load_method(method).steps.values():
        blanks = set(re.findall(r"\{(\w+)\}", step.say)) - known
        if blanks:
            assert step.say_plain, f"{method} step {step.id} needs say_plain"
            assert not set(re.findall(r"\{(\w+)\}", step.say_plain)) - known


def test_30_simulated_calls_never_show_a_rule_breaking_ai_sentence(fake_embedder):
    import random

    def rogue(prompt, n):
        return "ROGUE but you said any questions? $5k {x}"

    pool = [
        "I want to be free from my 9-5 and work from anywhere", "ten thousand a month",
        "about three years", "no time and no money", "will refunds exist?", "how much does it cost",
        "what do you do", "hold on a second", "it's too expensive", "I need to think about it",
        "yes that makes sense", "hmm", "purple banana", "yes let's do it",
    ]
    rng = random.Random(7)
    for _ in range(30):
        s = make_seller(fake_embedder, rogue, method=rng.choice(["cat", "impact_formula"]))
        lines = [s.opening()[0]] + [s.reply(rng.choice(pool))[0] for _ in range(12)]
        for line in lines:
            assert "ROGUE" not in line and "{" not in line, line
