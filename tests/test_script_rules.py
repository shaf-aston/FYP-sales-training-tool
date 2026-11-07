"""AI gap rules (checks, fill, judge) and the coach's selling rules, offline."""
import json
import logging

import pytest

from core.buy_mode.script_engine.ai.checks import CheckContext, check, clip
from core.buy_mode.script_engine.ai.judge import VAGUE, judge
from core.buy_mode.script_engine.engine import ScriptState
from core.buy_mode.script_engine.method import (
    load_common_sense,
    load_method,
    load_offer,
)
from core.buy_mode.script_engine.seller import ScriptSeller
from core.buy_mode.script_engine.words.fill import Filler
from core.infra.loader import CONFIG_DIR, load_yaml

CFG = load_yaml("script/engine.yaml")
OFFER = load_offer("shay_coaching")
METHODS = sorted(p.stem for p in (CONFIG_DIR / "methods").glob("*.yaml"))


def ctx(**kw):
    base = {"max_words": 30, "questions": 1, "price_ok": False, "price": "$5k",
            "banned_phrases": tuple(CFG["banned_phrases"])}
    return CheckContext(**{**base, **kw})


# ---- checks: one test per rule ------------------------------------------------------------

@pytest.mark.parametrize("text, kw, rule", [
    ("Why? Really?", {}, "question_count"),
    ("Nice point.", {}, "question_count"),
    ("It is fine but what next?", {}, "banned_phrase"),
    ("What did you mean when you said that?", {}, "banned_phrase"),
    ("Any questions?", {}, "banned_phrase"),
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


def _fill(slots=None, echo=frozenset(), say=STEP_SAY):
    slots = {"outcome": "I want financial freedom"} if slots is None else slots
    return Filler(CFG, OFFER, echo).render(say, "", STEP_PLAIN, slots)


def test_a_blank_not_marked_echo_gives_the_plain_line():
    # live: the AI wrote "feel your job freedom", "got to your 9 to 5" - plain lines always read right
    assert _fill() == STEP_PLAIN


def test_a_missing_answer_gives_the_plain_line():
    assert _fill(slots={}, echo={"outcome"}) == STEP_PLAIN


def test_fill_offer_blanks_come_from_the_offer():
    assert _fill({}, say="{months}-month process, investment is {price}.") == "6-month process, investment is $5k."


def test_ack_with_blank_is_dropped_when_it_cannot_be_filled():
    out = Filler(CFG, OFFER).render("Next?", "for {years} years.", "", {})
    assert out == "Next?"


def test_echo_says_their_words_back_in_second_person():
    say = "What would you do with {outcome}?"
    out = _fill({"outcome": "time with my kids"}, {"outcome"}, say)
    assert out == "What would you do with time with your kids?"
    long = {"outcome": "more time with my kids and my wife and my whole family"}  # over slot_words
    assert _fill(long, {"outcome"}, say) == STEP_PLAIN


CAT = load_method("cat")


def _line(step, reply):
    """The real script line for a step, with the buyer's step-01 answer echoed into it."""
    out = Filler(CFG, OFFER, {"outcome"}).render(
        CAT.steps[step].say, "", CAT.steps[step].say_plain, {"outcome": reply})
    return out


@pytest.mark.parametrize("reply, step, expected", [
    ("more time with my kids", "02", "to have more time with your kids?"),
    ("financial freedom", "05", "don't have financial freedom yet?"),
    ("I want to be my own boss", "02", "each month to be your own boss?"),
    ("quit my job", "05", "haven't managed to quit your job?"),
    ("travel the world with my wife", "06", "to travel the world with your wife rather than just dream about it?"),
    ("financial freedom", "06", "to get financial freedom rather than just dream about it?"),
    ("freedom I guess", "05", "don't have freedom yet?"),
    ("paying the bills", "02", "each month to pay the bills?"),             # an -ing goal is a verb goal
    ("travelling the world", "05", "haven't managed to travel the world?"),
    ("making more money", "06", "to make more money rather than just dream about it?"),
    ("being able to retire early", "02", "each month to retire early?"),
    ("debt free", "02", "each month to be debt free?"),                       # a state: "be" in front
    ("time freedom honestly", "05", "don't have time freedom yet?"),
    ("whatever, more money", "02", "each month to have more money?"),
])
def test_script_lines_echo_the_goal_in_noun_or_verb_form(reply, step, expected):
    assert expected in _line(step, reply)


@pytest.mark.parametrize("reply", [
    "honestly it is about being able to spend more time with my kids",  # 11 words
    "nothing", "nothing really", "I don't know", "no idea", "none",
    "I'm not giving you money",  # not a goal: "to have you're not giving you money"
])
def test_unusable_goal_gives_the_plain_line(reply):
    assert _line("02", reply) == CAT.steps["02"].say_plain


# ---- judge --------------------------------------------------------------------------------

CANDS = {"agrees": ["yes"], "unclear": ["I am lost"]}


def test_judge_picks_a_candidate_or_vague():
    assert judge("hm", CANDS, lambda p, n: "Agrees.", CFG) == "agrees"
    assert judge("hm", CANDS, lambda p, n: "no idea", CFG) == VAGUE
    assert judge("hm", CANDS, lambda p, n: "vague", CFG) == VAGUE


def test_judge_ai_down_counts_as_vague():
    def down(prompt, n):
        raise RuntimeError("down")

    assert judge("hm", CANDS, down, CFG) == VAGUE


# ---- seller: the coach's selling rules -----------------------------------------------------

class Vectors:
    """Embedder that maps a text to a chosen vector; unknown texts get an orthogonal one."""

    def __init__(self, table=None):
        self.table = table or {}

    def warm(self, texts):
        pass

    def embed(self, texts):
        return [self.table.get(t, [0.0, 0.0, 1.0]) for t in texts]


def fake_llm(prompt, max_tokens):
    """Answers a product question in one line; anything else is vague."""
    if "A prospect asked" in prompt:
        return "Yes, we offer mentorship."
    return "vague"


def make_seller(bow, llm=fake_llm, method="cat"):
    cfg = {**CFG, "threshold": 0.5}
    return ScriptSeller(cfg, load_method(method), OFFER, load_common_sense(), bow, llm)


@pytest.fixture
def seller(fake_embedder):
    return make_seller(fake_embedder)


def at(seller, step, **slots):
    seller.reset(ScriptState(step=step, slots=slots))
    return seller


def test_price_early_gets_one_line_then_first_questions(seller):
    text, _ = at(seller, "03", outcome="I want financial freedom").reply("how much does it cost")
    assert "exact price once I know what you need" in text
    assert "$5k" not in text
    assert text.endswith("How long have you been thinking about this?")
    assert seller.state.step == "03"


def test_what_do_you_do_mid_call_gets_the_intro_then_the_step_question(seller):
    text, _ = at(seller, "03").reply("what do you do")
    assert text.startswith("We help people build their own business online")
    assert "programme" not in text and "$5k" not in text
    assert text.endswith("How long have you been thinking about this?")


def test_price_after_price_step_is_stated(seller):
    text, _ = at(seller, "18").reply("how much does it cost")
    assert "$5k" in text and "6-month" in text


@pytest.mark.parametrize("name, said", [
    ("money", "it's too expensive"),
    ("think", "I need to think about it"),
    ("research", "let me do some more research first"),
])
def test_an_objection_at_the_close_enters_its_matrix_branch(seller, name, said):
    enter = seller.method.objections[name].enter
    text, _ = at(seller, "19").reply(said)
    assert text.endswith(seller.method.steps[enter].say)
    assert seller.state.step == enter and seller.state.raised == (name,)


def test_objection_before_the_price_is_acknowledged_then_the_question_comes_back(seller):
    # live call: "I need to think about it" mid-discovery got the next question as if unheard
    text, _ = at(seller, "03", outcome="I want financial freedom").reply("I need to think about it")
    assert text.startswith(seller.sense.park)
    assert text.endswith("How long have you been thinking about this?")
    assert seller.state.step == "03" and seller.state.parked == ("think",)


def test_a_new_objection_gets_its_branch_until_the_limit_then_the_follow_up_is_booked(seller):
    at(seller, "19").reply("it's too expensive")
    seller.reply("I need to think about it")
    assert seller.state.step == "m_think_what" and seller.state.raised == ("money", "think")
    seller.reply("is this a scam?")  # a third worry in one call is a smokescreen
    assert seller.state.step == seller.method.follow_up


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
    assert text.startswith("Yes, we offer mentorship.")
    assert text.endswith(" How long have you been thinking about this?")
    assert json.loads(caplog.records[0].message)["question"] == "will refunds exist?"
    assert seller.state.step == "03"


def test_uncovered_question_with_a_rule_breaking_answer_is_dropped(fake_embedder, caplog):
    def pushy(prompt, n):
        return "It is $5k but worth it." if "A prospect asked" in prompt else fake_llm(prompt, n)

    s = at(make_seller(fake_embedder, pushy), "03")
    with caplog.at_level(logging.WARNING, logger="script_engine.fallback"):
        text, _ = s.reply("will refunds exist?")
    assert text == f"{CFG['uncovered_fallback']} How long have you been thinking about this?"
    assert "broke" in caplog.text


def test_ai_down_never_blocks_a_turn(fake_embedder):
    def down(prompt, n):
        raise RuntimeError("down")

    s = at(make_seller(fake_embedder, down), "03", outcome="I want financial freedom")
    text, _ = s.reply("will refunds exist?")
    assert text == f"{CFG['uncovered_fallback']} How long have you been thinking about this?"
    text, _ = at(s, "02", outcome="I want financial freedom").reply("ten thousand")
    assert text == "How long have you been thinking about this?"
    text, _ = at(s, "05", outcome="I want financial freedom").reply("no time")
    assert text == "What are you doing now to get financial freedom rather than just dream about it?"  # no AI needed
    text, _ = at(s, "05", outcome="I want to quit my job").reply("no time")
    assert text == "What are you doing now to quit your job rather than just dream about it?"  # verb form
    text, _ = at(s, "05", outcome="I want to be my own boss").reply("no time")
    assert text == "What are you doing now to make that a reality and not just a dream?"  # 4 words: waits for a moment
    text, _ = at(s, "05", outcome="nothing really").reply("no time")
    assert "that" in text and "{" not in text    # no goal said: say_plain used for step 06


def test_common_sense_interruption_then_the_step_again(seller):
    s = at(seller, "03", why="more time with my kids")
    # a pause gets a short reply and the bot waits, like a person would
    assert s.reply("hold on a second") == ("No problem, take your time.", "logical")
    text, stage = s.reply("ok I'm back")
    assert text.startswith("No worries.")
    assert text == "No worries. How long have you been thinking about this?"
    assert stage == "logical" and s.state.step == "03"


def _close_call_seller(llm):
    bow = Vectors()
    cat = load_method("cat")
    for route in cat.steps["18"].listen:
        for example in route.examples:
            bow.table[example] = [0.8, 0.6 if route.label == "agrees" else -0.6, 0.0]
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
    assert text == s.method.steps["18"].probes[0]  # asked again in simpler words, not repeated


def test_replay_gives_the_same_lines(fake_embedder):
    replies = ["I want to be free from my 9-5 and work from anywhere", "ten thousand", "3 years"]

    def run():
        s = make_seller(fake_embedder)
        return [s.opening()[0]] + [s.reply(r)[0] for r in replies]

    assert run() == run()


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
        s = make_seller(fake_embedder, rogue, method=rng.choice(METHODS))
        lines = [s.opening()[0]] + [s.reply(rng.choice(pool))[0] for _ in range(12)]
        for line in lines:
            assert "ROGUE" not in line and "{" not in line, line


# ---- review fixes -------------------------------------------------------------------------

def make_seller_with(bow, llm=fake_llm, **override):
    cfg = {**CFG, "threshold": 0.5, **override}
    return ScriptSeller(cfg, load_method("cat"), OFFER, load_common_sense(), bow, llm)


def _uncovered_records(caplog):
    return [r for r in caplog.records if r.name == "script_engine.uncovered"]


def test_a_judged_close_call_survives_rewind_and_replay():
    from core.buy_mode.seller_bot import SellerBot

    bot = SellerBot(provider_type="dummy", product_type="high_ticket_sales_mentorship")
    bot.seller = at(_close_call_seller(lambda p, n: "agrees"), "18")
    bot.chat("hmm")                       # borderline: the judge says "agrees" -> step 19
    assert bot.seller.state.step == "19"
    bot.chat("purple banana")             # no match: stays on 19
    bot.rewind_to_turn(1)                 # the stored turn state is restored, nothing is re-judged
    assert bot.seller.state.step == "19"


def test_objection_lines_are_filled_like_any_other_line(seller):
    at(seller, "19")
    line, _ = seller.reply("it's too expensive")
    assert "{" not in line


def test_ai_is_skipped_for_the_rest_of_a_turn_after_one_failure(fake_embedder):
    calls = []

    def down(prompt, n):
        calls.append(prompt)
        raise RuntimeError("down")

    s = at(make_seller(fake_embedder, down), "03", why="more time with my kids")
    s.reply("will refunds exist?")
    assert len(calls) == 1                # answer attempt failed; bring-back and fills never asked
    s.reply("will refunds exist?")
    assert len(calls) == 2                # the next turn tries the AI again


def _gate(**override):
    from core.buy_mode.script_engine.ai.gate import AiGate
    return AiGate({**CFG, **override})


def test_slow_ai_is_abandoned():
    import time

    class Slow:
        def chat_with_fallback(self, messages, max_tokens):
            time.sleep(0.5)

    assert CFG["ai_timeout_seconds"] > 0
    llm = _gate(ai_timeout_seconds=0.05, ai_rest_seconds=60, ai_fail_limit=1).llm(Slow())
    with pytest.raises(TimeoutError):
        llm("hi", 5)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="resting"):
        llm("hi", 5)  # after the limit the AI is skipped at once, not waited on again
    assert time.monotonic() - started < 0.05


class _Flaky:
    """A provider that fails while `down` is set."""

    def __init__(self):
        self.down, self.calls = True, 0

    def chat_with_fallback(self, messages, max_tokens):
        from types import SimpleNamespace
        self.calls += 1
        if self.down:
            return SimpleNamespace(ok=False, response=SimpleNamespace(error="down", content=""))
        return SimpleNamespace(ok=True, response=SimpleNamespace(error=None, content="fine"))


def test_one_failure_does_not_rest_the_ai_for_everyone():
    router = _Flaky()
    llm = _gate(ai_timeout_seconds=1, ai_rest_seconds=60, ai_fail_limit=3).llm(router)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="down"):
            llm("hi", 5)
    router.down = False
    assert llm("hi", 5) == "fine"          # still tried after two failures, and a success resets the count
    router.down = True
    for _ in range(2):
        with pytest.raises(RuntimeError, match="down"):
            llm("hi", 5)
    assert router.calls == 5               # two new failures: under the limit again, nothing skipped
    with pytest.raises(RuntimeError, match="down"):
        llm("hi", 5)                       # third in a row
    with pytest.raises(RuntimeError, match="resting"):
        llm("hi", 5)
    assert router.calls == 6


def test_uncovered_answer_is_fenced_and_must_stay_inside_the_facts(fake_embedder):
    prompts = []

    def llm(prompt, n):
        prompts.append(prompt)
        return "Visit example.com or call 555 1234 for details."

    s = at(make_seller(fake_embedder, llm), "03")
    text, _ = s.reply("will refunds exist?")
    assert "<question>will refunds exist?</question>" in prompts[0]
    assert text.startswith(CFG["uncovered_fallback"])


def test_checks_reject_new_numbers_and_banned_words():
    c = ctx(questions=0, price_ok=True, known_figures=frozenset({"6 month"}), banned=frozenset({"guarantee"}))
    assert check("It is a 6-month programme.", c) == []
    assert check("It runs for 6 months.", c) == []
    assert check("Most people see results in 8 weeks.", c) == ["new_number"]
    assert check("You get 6 coaching calls.", c) == ["new_number"]   # a known number counting something new
    assert check("We guarantee you'll love it.", c) == ["banned_word"]


def test_judge_needs_exactly_one_label():
    assert judge("hm", CANDS, lambda p, n: "agrees or unclear", CFG) == VAGUE


def test_logged_prospect_text_is_clipped_and_logging_can_be_switched_off(fake_embedder, caplog):
    long_question = "will " + " ".join(f"w{i}" for i in range(80)) + " exist?"
    with caplog.at_level(logging.INFO, logger="script_engine.uncovered"):
        at(make_seller_with(fake_embedder), "03").reply(long_question)
    logged = json.loads(_uncovered_records(caplog)[0].message)["question"]
    assert len(logged) <= CFG["log_text_chars"] + 3
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="script_engine.uncovered"):
        at(make_seller_with(fake_embedder, log_uncovered=False), "03").reply("will refunds exist?")
    assert not _uncovered_records(caplog)
    assert clip("abc", 5) == "abc"


def test_uncovered_question_is_logged_even_when_the_ai_is_down(fake_embedder, caplog):
    def down(prompt, n):
        raise RuntimeError("down")

    with caplog.at_level(logging.INFO, logger="script_engine.uncovered"):
        at(make_seller(fake_embedder, down), "03").reply("will refunds exist?")
    assert json.loads(_uncovered_records(caplog)[0].message) == {"question": "will refunds exist?", "answer": None}


def test_a_question_word_without_a_question_mark_still_counts(fake_embedder):
    text, _ = at(make_seller(fake_embedder), "03").reply("are there refunds")
    assert text.startswith("Yes, we offer mentorship.")


@pytest.mark.parametrize("text, expected", [
    ("what I want is freedom", False),
    ("why can't I ignore it, because it keeps me up", False),
    ("how much is it", True),
    ("will refunds exist?", True),
    ("is this legit", True),
    ("isnt this just a scam", True),
    ("have you got any proof", True),
    ("how do I know it works", True),
    ("who are you", True),
    ("what is this call about", True),
    ("do it for my kids", False),
    ("have a family to look after", False),
    ("can't afford it", False),
    ("how I see it is I need more time", False),
    ("shut up and just tell me the price", True),   # live: moved on as their answer
    ("ok fine, how much is it", True),
    ("I want freedom and time with my kids", False),
    ("how'd you get my number", True),   # live: "Good to know."
    ("yeah but how much is it", True),   # a question after "but" or "so" is a question part
    ("ok so what's the price", True),
    ("bro, you get me?", False),   # a filler tag, not a question
    ("wait, sorry, what's this going to cost me?", True),   # "what's" is "what": never an answer said with a rise
    ("whats the catch?", True),
])
def test_question_detection_uses_the_opening_words_or_a_question_mark(text, expected):
    from core.buy_mode.script_engine.hear.reply import Reader
    reply = Reader(CFG, (), lambda part: False).read(text).settle(lambda part: False)  # a rise asks unless the step says
    assert bool(reply.asked) is expected


HEDGES = {"i guess", "idk", "lol idk", "honestly no idea"}   # stands in for the real model's "unclear" match


@pytest.mark.parametrize("text, said, asked", [
    ("i guess 3 years, what about you?", "i guess 3 years", "what about you?"),   # live: the 3 years was lost
    ("honestly no idea, 3 years?", "3 years", ""),   # a hedge part is left out
    ("nothing, why do you ask?", "nothing", "why do you ask?"),
    ("two years, and what's the price", "two years", "what's the price"),
    ("lol idk, money?", "money", ""),   # a "?" after a hedge is an unsure answer
    ("time and money tbh", "time and money tbh", ""),   # nothing left out: the reply as typed
    ("credit, what's next?", "credit", ""),   # the nudge is cut off its end
    ("it's 2.5k, is that ok?", "it's 2.5k", "is that ok?"),   # "2.5k" is never cut at its point
    ("3k, no wait, more like 4k", "more like 4k", ""),   # whole calls: the 3k they took back was kept
    ("3 years, sorry, 2 years", "2 years", ""),
    ("pay off my car, no actually my credit card", "my credit card", ""),
    ("sorry, where were we?", "", "where were we?"),   # was "sorry" taken as their answer
    ("wait, sorry, what's this going to cost me?", "", "what's this going to cost me?"),   # one after another
    ("nothing, sorry", "nothing, sorry", ""),   # nothing after it: nothing taken back
    ("sorry my dog is barking", "sorry my dog is barking", ""),   # one word takes back only with a break after it
    ("a year, no, two years", "two years", ""),   # whole calls: "no" between two parts corrects the first
    ("credit, no, debit", "debit", ""),
    ("no, credit?", "no", "credit?"),   # "no" at the start says no, takes nothing back
    ("no, no, I can't", "no, no, I can't", ""),   # "no" after "no" says no again
    ("I said no, debit", "I said no, debit", ""),   # "no" with no break before it is a word, not a correction
    ("hang on a minute, that's a lot of money", "that's a lot of money", ""),   # whole calls: torn with a pause, saved as a yes
    ("hold on, how much?", "", "how much?"),   # whole calls: heard as unclear, the price never said
    ("hold on a second", "hold on a second", ""),   # a pause with no break after it is the pause
    ("hang on my phone is dying", "hang on my phone is dying", ""),
])
def test_a_reply_is_read_once_into_what_it_says_and_what_it_asks(text, said, asked):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    reply = Reader(CFG, load_common_sense().nudges, lambda part: part.lower() in HEDGES).read(text)
    reply = reply.settle(lambda part: False)
    assert (reply.said, reply.asked) == (said, asked)


def test_a_line_asked_again_is_filled_the_same_way_without_new_ai_calls(fake_embedder):
    calls = []

    def llm(prompt, n):
        calls.append(prompt)
        return ["travel", "more money"][len(calls) % 2 - 1]

    s = at(make_seller(fake_embedder, llm), "05", outcome="I want to travel the world")
    first = s.reply("hold on a second")
    again = s.reply("ok I'm back")[0]
    asked = calls.copy()
    assert first[0] == "No problem, take your time."
    s.reply("hold on a second")
    assert s.reply("ok I'm back")[0] == again and calls == asked


def test_im_back_is_an_answer_unless_they_stepped_away(fake_embedder):
    s = at(make_seller(fake_embedder), "04", why="more time with my kids")
    s.reply("ok I'm back")
    assert s.state.step != "04"  # step 04 takes any answer, so the script moved on


def test_the_same_worry_said_again_in_its_branch_answers_the_step(seller):
    at(seller, "19").reply("it's too expensive")
    seller.reply("it's too expensive")  # "no, I can't afford it" answers m_funded; it is not a new objection
    assert seller.state.raised == ("money",) and seller.state.step != seller.method.follow_up


def test_scripted_coaching_note_comes_from_the_step_without_ai(fake_embedder):
    def no_ai(prompt, n):
        raise AssertionError("coaching notes must not call the AI")

    s = at(make_seller(fake_embedder, no_ai), "05")
    notes = s.coach_notes()
    assert notes["what_happened"] == "The seller is finding out about your blocker."
    assert notes["next_move"].startswith("Listen for: externalising")


def test_checked_line_retries_then_gives_up_on_rule_breaking_ai():
    """Every AI sentence goes through one loop: a bad line is retried, never used."""
    from core.buy_mode.script_engine.ai.checks import CheckContext
    from core.buy_mode.script_engine.ai.line import checked_line

    cfg = {"ai_retries": 1, "log_text_chars": 50}
    ctx = CheckContext(max_words=10, questions=0, price_ok=False, price="£3000")
    answers = iter(["It costs £3000?", "It is a six month programme."])
    assert checked_line(lambda p, n: next(answers), "q", 20, ctx, cfg, "t") == "It is a six month programme."
    assert checked_line(lambda p, n: "It costs £3000.", "q", 20, ctx, cfg, "t") is None

    def down(p, n):
        raise RuntimeError("offline")
    assert checked_line(down, "q", 20, ctx, cfg, "t") is None




# ---- listening: what the live roleplay report found -------------------------------------

def test_people_like_me_is_answered_as_fit_not_location(seller):
    # live: "do people like me actually make it work" got "We work with people all around the world."
    text, _ = at(seller, "03").reply("do people like me actually make it work")
    assert text.startswith(seller.offer.facts["fit"].answer)
    assert "around the world" not in text


def test_ok_to_an_open_question_is_asked_again_then_the_call_moves_on(seller):
    # live: "ok" to "how long have you been thinking about this" was taken as the answer
    at(seller, "03", outcome="freedom")
    again, _ = seller.reply("ok")
    assert seller.state.step == "03" and again == "Roughly, is it more like months, or a few years?"
    for _ in range(CFG["misses"] - 1):  # probes ran out: back to the question behind a lead, never moved on early
        last, (again, _) = again, seller.reply("sure")
        assert seller.state.step == "03" and again.endswith("How long have you been thinking about this?")
        assert not again.endswith(last)  # the same words twice in a row read like a bot
    seller.reply("sure")
    assert seller.state.step == "04" and "years" not in seller.state.slots


def test_sure_is_not_read_as_asking_to_repeat(seller):
    # live: "sure" got "Of course, let me ask that again."
    text, _ = at(seller, "01").reply("sure")
    assert seller.sense.interruptions["repeat"].reply not in text
    assert text == seller.method.steps["01"].probes[0]


def test_yeah_still_answers_a_yes_no_step(seller):
    at(seller, "18").reply("yeah")
    assert seller.state.step == "19"


def test_no_is_a_real_answer(seller):
    at(seller, "06").reply("no")
    assert seller.state.step != "06"


def test_back_after_a_pause_still_works(seller):
    at(seller, "03")
    seller.reply("hold on a second")
    text, _ = seller.reply("ok I'm back")
    assert text.startswith(seller.sense.interruptions["back"].reply)


def test_scam_question_before_the_price_gets_an_honest_line_and_is_remembered(seller):
    # live: "is this a scam?" got "Good question, I'll confirm that for you after the call."
    text, _ = at(seller, "03").reply("is this a scam?")
    assert text.startswith(seller.method.objections["scam"].early)
    assert text.endswith("How long have you been thinking about this?")
    assert seller.state.parked == ("scam",)


def test_a_worry_is_parked_once(seller):
    at(seller, "03")
    seller.reply("I can't afford that right now")
    seller.reply("I can't afford that right now")
    assert seller.state.parked == ("money",)


def test_price_question_still_gets_the_price_fact_not_the_money_worry(seller):
    for asked in seller.offer.facts["price"].examples:
        text, _ = at(seller, "03").reply(asked)
        assert text.startswith(seller.offer.facts["price"].answer), asked
        assert seller.state.parked == ()


def test_a_parked_worry_comes_back_when_they_hesitate_at_the_close(seller):
    # live: the scam worry was brushed off and never handled
    at(seller, "19")
    seller.reset(ScriptState(step="19", parked=("partner",)))
    text, _ = seller.reply("no, not really")
    enter = seller.method.objections["partner"].enter
    assert text == f"{seller.sense.revisit} {seller.method.steps[enter].say}"
    assert seller.state.step == enter and seller.state.parked == () and seller.state.raised == ("partner",)


def test_parked_worries_survive_a_rewind_snapshot():
    from dataclasses import asdict

    state = ScriptState(step="05", parked=("scam", "money"))
    restored = ScriptState(**asdict(state))
    assert tuple(restored.parked) == ("scam", "money")


@pytest.mark.parametrize("change, error", [
    ({"revisit_step": "03"}, "revisit_step"),
    ({"revisit_step": ""}, "revisit_step"),
    ({"objections.money.examples": []}, "examples"),
    ({"objections.money.early": "Is money the issue?"}, "early line"),
])
def test_broken_revisit_settings_fail_loud(change, error):
    from core.buy_mode.script_engine.method import CONFIG_DIR, _read, parse_method

    data, matrix = _read(CONFIG_DIR / "methods", "cat"), _read(CONFIG_DIR / "script", "objection_matrix")
    (key, value), = change.items()
    if key.startswith("objections."):
        _, name, field_ = key.split(".")
        matrix["objections"][name][field_] = value
    else:
        data[key] = value
    with pytest.raises(ValueError, match=error):
        parse_method("cat", data, matrix, _read(CONFIG_DIR / "script", "answers"))


def test_a_route_like_a_shared_answer_hears_it_and_its_own_examples():
    # one list per meaning (answers.yaml): "credit" was a yes at one "jumping in?" and unclear at the other
    from core.buy_mode.script_engine.method import load_method

    method = load_method("cat")
    for step in ("19", "m_partner_close", "m_close1", "m_close2", "m_close3"):   # every "jumping in?"
        pays = next(r for r in method.steps[step].listen if r.label == "pays")
        assert "credit" in pays.examples and pays.then == "22"   # a way to pay goes to paying
    card = next(r for r in method.steps["m_card"].listen if r.label == "yes").examples
    assert card[0] == "yes" and "ok let's put it on a card" in card and len(card) == len(set(card))


def test_a_route_like_an_unknown_answer_fails_loud():
    from core.buy_mode.script_engine.method import CONFIG_DIR, _read, parse_method

    data, matrix = _read(CONFIG_DIR / "methods", "cat"), _read(CONFIG_DIR / "script", "objection_matrix")
    data["steps"]["19"]["listen"]["agrees"]["like"] = "jump_inn"
    with pytest.raises(ValueError, match="unknown answer 'jump_inn'"):
        parse_method("cat", data, matrix, _read(CONFIG_DIR / "script", "answers"))


def test_is_this_a_bot_gets_an_honest_yes_then_the_question(seller):
    # live: "is this a bot?" was dodged with "I'll confirm that for you after the call"
    text, _ = at(seller, "03").reply("is this a bot?")
    assert text.startswith(seller.sense.interruptions["bot"].reply)
    assert text.endswith("How long have you been thinking about this?")


def test_why_do_you_keep_asking_moves_to_other_words_and_counts_toward_moving_on(seller):
    # live: "what do you mean freedom" / "why do you keep asking" got the same question again
    probes = seller.method.steps["01"].probes
    text, _ = at(seller, "01").reply("why do you keep asking the same thing")
    assert text == f'{seller.sense.interruptions["clarify"].reply} {probes[0]}'
    assert seller.state.asks == 1


def test_repeat_and_unclear_still_win_their_own_phrases(seller):
    text, _ = at(seller, "03").reply("sorry, can you say that again")
    assert text.startswith(seller.sense.interruptions["repeat"].reply)
    at(seller, "18").reply("can you explain that again")
    assert seller.state.step == "18"


def _acking(ack, calls=None):
    """fake_llm plus an ack answer; records the prompts it was sent."""
    def llm(prompt, n):
        if calls is not None:
            calls.append(prompt)
        if "<goal>" in prompt:  # the listen call: they answered, here is the ack
            return f"ANSWERED: yes\nACK: {ack}\nPROBE: none"
        if "shows you heard them" in prompt:
            return ack
        return fake_llm(prompt, n)
    return llm


def test_their_words_are_heard_before_the_next_question(fake_embedder):
    # live: "I work nights and barely see my daughter" got the next question as if unheard
    seller = at(make_seller(fake_embedder, _acking("That sounds hard, you barely see your daughter.")), "04")
    text, _ = seller.reply("I work nights and barely see my daughter")
    assert text.startswith("That sounds hard, you barely see your daughter. ")
    assert text.endswith(seller.method.steps["05"].say_plain)


@pytest.mark.parametrize("bad", [
    "Great, you are seeing your daughter less.",    # "great" and "seeing" are not their words
    "Why do you barely see your daughter?",          # a question
    "You barely see your daughter, $5k fixes that.",  # price before the price step
])
def test_an_ack_that_breaks_a_rule_is_left_out(fake_embedder, bad):
    seller = at(make_seller(fake_embedder, _acking(bad)), "04")
    text, _ = seller.reply("I work nights and barely see my daughter")
    assert text == seller.method.steps["05"].say_plain


def test_no_ack_call_when_the_route_has_its_own(fake_embedder):
    calls = []
    seller = at(make_seller(fake_embedder, _acking("You tried dropshipping.", calls)), "03")
    text, _ = seller.reply("I tried dropshipping and it failed")
    assert text.startswith("Sorry to hear that")
    assert not any("shows you heard them" in p for p in calls)


def test_no_ack_for_a_reply_that_says_nothing(fake_embedder):
    calls = []
    seller = at(make_seller(fake_embedder, _acking("Okay.", calls)), "03")
    seller.reply("ok")
    assert calls == []


def test_ai_down_means_no_ack_and_no_canned_line(fake_embedder):
    def down(prompt, n):
        raise RuntimeError("offline")
    seller = at(make_seller(fake_embedder, down), "04")
    text, _ = seller.reply("I work nights and barely see my daughter")
    assert text == seller.method.steps["05"].say_plain


def test_the_ack_comes_before_run_on_lines(fake_embedder):
    seller = at(make_seller(fake_embedder, _acking("You can see it.")), "20")
    text, _ = seller.reply("I see myself in it")
    assert text.startswith("You can see it. ")
    assert seller.method.steps["21"].say in text


def test_not_sure_what_you_mean_is_not_taken_as_the_gap_answer(seller):
    # live check: "not sure what you mean" at 08 was saved as their answer and the script moved on
    text, _ = at(seller, "08").reply("not sure what you mean")
    assert text.startswith(seller.sense.same_words)   # 08 has no other words: asked again, never "another way"
    assert seller.state.step == "08"


def test_last_turn_says_what_the_reply_was_heard_as(seller):
    at(seller, "08").reply("not sure what you mean")
    assert seller.last_turn["heard_as"] == "sense:clarify"
    assert seller.last_turn["step_from"] == seller.last_turn["step_to"] == "08"
    at(seller, "08").reply("taking risks and making decisions")
    assert seller.last_turn["heard_as"] == "answer:any"
    assert seller.last_turn["step_from"] == "08" != seller.last_turn["step_to"]


def test_a_typo_is_fixed_before_the_reply_is_understood(seller):
    # live check: "financialy freedom" at 01 was heard as unclear and the question was asked again
    at(seller, "01").reply("financialy freedom")
    assert seller.last_turn["heard_as"] != "answer:unclear"
    assert seller.state.slots["outcome"] == "financial freedom"


def test_a_price_question_at_the_price_step_gets_the_price_once(seller):
    # live: "how much is it again?" got "...investment is $5k. 6-month process, investment is $5k..."
    text, _ = at(seller, "14").reply("how much is it again?")
    assert text.count("$5k") == 1


def test_how_long_they_have_thought_about_it_is_said_back_in_months(seller):
    # owner: "2 years" -> "24 months... Damn." in its own bubble, then the why question
    text, _ = at(seller, "03").reply("2 years")
    assert text.startswith("24 months... Damn.¶") and "why can't you just ignore it?" in text


def test_the_pays_shortcut_is_open_from_the_price_until_the_soft_close():
    from core.buy_mode.script_engine.engine import ready_open
    from core.buy_mode.script_engine.method import load_method

    method = load_method("cat")
    open_at = [s for s in method.steps if ready_open(method, s, method.pays)]
    assert open_at == ["14", "15", "16", "17", "18"] and "credit" in method.pays.examples
    assert not ready_open(method, "13") and not ready_open(method, "14")   # the keen-buyer one shuts at the pitch


def test_a_shortcut_whose_from_is_not_before_its_until_fails_loud():
    from core.buy_mode.script_engine.method import CONFIG_DIR, _read, parse_method

    data, matrix = _read(CONFIG_DIR / "methods", "cat"), _read(CONFIG_DIR / "script", "objection_matrix")
    data["pays"] = {**data["pays"], "from": "19"}
    with pytest.raises(ValueError, match="from must come before its until"):
        parse_method("cat", data, matrix, _read(CONFIG_DIR / "script", "answers"))


def test_no_two_closes_ask_jumping_in_word_for_word():
    """Sid heard "Do you see yourself jumping in?" four times, word for word (19, then each reframe's close)."""
    steps = ("19", "m_partner_close", "m_close1", "m_close2", "m_close3")
    says = [CAT.steps[s].say for s in steps]
    assert len(set(says)) == len(says), says


@pytest.mark.parametrize("step", ["19", "m_partner_close", "m_close1", "m_close2", "m_close3", "13", "m_funded", "m_partner_proceed", "m_partner_here", "m_reframe1_now", "m_reframe1_dictate"])
def test_a_question_with_a_lead_in_is_still_a_yes_or_no(fake_embedder, step):
    """A lead-in before the helper verb ("With all that in mind, do you...", "So if ..., would you...") keeps it yes or no."""
    assert make_seller(fake_embedder)._ear._yes_or_no(ScriptState(step=step))


@pytest.mark.parametrize("step", ["01", "goal_identity", "m_partner_feel", "m_partner_if_not", "m_reframe2", "22"])
def test_an_open_question_with_a_lead_in_is_not_a_yes_or_no(fake_embedder, step):
    """"So, How does your partner feel...?", "Well, what are you going to do...?": the lead-in hides no helper verb."""
    from dataclasses import replace
    state = ScriptState(step=step)
    if CAT.steps[step].probes:
        state = replace(state, asks=1)  # 19's probe: "Where are you at with it right now?"
    assert not make_seller(fake_embedder)._ear._yes_or_no(state)


@pytest.mark.parametrize("text, part, rest", [
    ("make money online so I can quit my job", "make money online", "so I can quit my job"),
    ("money, so I can rest!", "money", "so I can rest"),   # the break and the end are trimmed
    ("time, more time", "time", "more time"),               # from the first time it comes
    ("make money online.", "make money online", ""),       # nothing after it
    ("make money online", "quit", ""),                     # not in the reply
    ("make money online", "", ""),
])
def test_after_a_part_is_what_follows_it(text, part, rest):
    from core.buy_mode.script_engine.hear.reply import after
    assert after(text, part) == rest


def test_after_restated_is_what_follows_the_part_that_says_the_question_back(seller):
    said_back = {"restated": ["it's a long story"]}
    assert seller._after_restated("it's a long story, so I can cut down my hours", said_back) == "so I can cut down my hours"
    assert seller._after_restated("so I can cut down my hours, it's a long story", said_back) == ""
    assert seller._after_restated("it's a long story", said_back) == ""


@pytest.mark.parametrize("part, rises", [
    ("a year?", True), ("because money is nice?", True), ("cos I need it, honestly?", True),
    ("about a year or so I would say really?", False),   # longer than `rise_answer_words`: a question
    ("one two three four five years?", True),            # exactly `rise_answer_words`
    ("ok?", True), ("yeah?", True),                      # round 16: only filler asks nothing, "ok?" got "I'll find out"
])
def test_a_rise_is_an_answer_when_short_and_shaped_or_a_reason(seller, part, rises):
    assert seller._ear._rises(part, seller.method.steps["03"]) == rises


def test_an_answer_with_a_worry_beside_it_keeps_the_answer(seller):
    """Round 16: "make money online, but I've been burnt before" lost the goal to the worry's early line."""
    text, _ = at(seller, "01").reply("make money online, but I'm scared it won't work for me")
    assert seller.last_turn["heard_as"] == "answer:vague+objection:fear", seller.last_turn
    assert text.startswith("That's fair") and text.endswith("What do you mean by wanting to make money online?"), text


def test_an_answer_beside_a_worry_keeps_a_later_answer_too(seller):
    """"I want to make 5k a month, but...": the 5k is kept for "how much?", as without the worry."""
    at(seller, "01").reply("I want to make 5k a month, but I'm scared it won't work for me")
    assert seller.last_turn["heard_as"].endswith("+objection:fear"), seller.last_turn
    assert seller.state.slots == {"number": "5k a month"}, seller.state.slots


def test_a_worry_beside_an_interruption_is_only_the_worry(seller, monkeypatch):
    """"brb, but I'm scared it won't work" is the worry: "brb" is never kept as the answer. Each part is heard
    as said before the price, as a statement, and the rest without its "but"."""
    heard = []

    def interrupt(text, step, state, opened, asking, answers=True):
        heard.append((text, opened, asking))
        return {"brb": ("sense", "pause"), "I hate my job": (None, "")}.get(text, ("objection", "fear"))

    monkeypatch.setattr(seller._ear, "_interrupt", interrupt)
    ear, state = seller._ear, ScriptState(step="04")
    step = ear.method.steps["04"]
    assert ear._beside_worry("brb, but I'm scared it won't work", step, state, "fear") is None
    v = ear._beside_worry("I hate my job, but I'm scared, it won't work", step, state, "fear")
    assert (v.kind, v.text, v.side) == ("answer", "I hate my job", "objection:fear"), v
    assert ("I'm scared, it won't work", False, False) in heard, heard
    assert all(h[1:] == (False, False) for h in heard), heard


def test_a_plain_no_is_never_an_interruption(seller, monkeypatch):
    """Round 17: "nah" (0.76 to "huh") got "Fair point, let me put it another way"; it is a no, an answer."""
    monkeypatch.setattr(seller._ear, "_interrupt", lambda *a, **k: ("sense", "clarify"))
    assert seller._ear.hear("nah", ScriptState(step="01"), False).kind == "answer"
    assert seller._ear.hear("huh", ScriptState(step="01"), False).kind == "sense"   # guard: anything else is heard


@pytest.mark.parametrize("step, slots, said, kept", [
    ("03", {"number": "2k"}, "sorry I meant 3k not 2k", {"number": "3k"}),   # round 17: saved as how long
    ("04", {"years": "a year"}, "make that 18 months", {"years": "18 months"}),
    ("goal_practical", {"outcome": "more money"}, "I meant freedom, not money", {"outcome": "freedom"}),
    ("03", {"number": "2k"}, "sorry I meant 3k.", {"number": "3k"}),   # the stop is not kept
    ("03", {"number": "2k"}, "sorry I meant 3k NOT 2k", {"number": "3k"}),   # any case
    ("04", {"years": "a year"}, "make that 18 MONTHS", {"years": "18 MONTHS"}),
])
def test_an_answer_fixed_a_turn_later_replaces_it(seller, step, slots, said, kept):
    text, _ = at(seller, step, **slots).reply(said)
    assert seller.state.slots == kept and seller.state.step == step, (text, seller.state)
    assert text.startswith("Got it, thanks."), text


@pytest.mark.parametrize("step, slots, said", [
    ("03", {"number": "2k"}, "I meant what I said"),        # no figure: no fix to "how much"
    ("05", {"years": "a year"}, "I meant to start ages ago"),  # "meant to" is no fix
    ("02", {}, "I meant 3k"),                               # nothing saved yet
])
def test_only_a_real_fix_replaces_an_answer(seller, step, slots, said):
    at(seller, step, **slots).reply(said)
    assert seller.last_turn["heard_as"] != "corrects:" + next(iter(slots), ""), seller.last_turn
    for k, v in slots.items():
        assert seller.state.slots[k] == v


def test_a_fix_on_the_step_still_asked_is_its_answer(seller):
    """On the step that saved it, "I meant 3k" is that step's answer again, not a fix of an earlier one."""
    assert seller._ear._correction("sorry I meant 3k", ScriptState(step="02", slots={"number": "2k"})) is None
    assert seller._ear._correction("sorry I meant 3k", ScriptState(step="03", slots={"number": "2k"})).text == "3k"


@pytest.mark.parametrize("step, said", [
    ("01", "what do I want to achieve?"),                # round 19: got "I'm the AI playing the salesperson"
    ("goal_practical", "what would it get me?"),         # round 19: got "I'll find out"
    ("04", "why can't I ignore it?"),
    ("19", "do I see myself jumping in?"),
    ("goal_identity", "what would it change?"),          # round 19: no I-word, got "I'll find out"
    ("03", "how long?"),                                 # round 19: was heard as "recent"
    ("03", "how long what?"),                            # round 20: the "what?" made it 2 of 3, moved on unanswered
])
def test_the_question_said_back_asks_it_another_way(seller, step, said):
    v = seller._ear.hear(said, ScriptState(step=step), False)
    assert (v.kind, v.name, v.text, v.asking) == ("sense", "clarify", said, True), v
    text, _ = at(seller, step).reply(said)
    assert seller.last_turn["heard_as"] == "sense:clarify", seller.last_turn
    assert text.startswith("Fair point, let me put it another way."), text


@pytest.mark.parametrize("step, said", [
    ("01", "what do you do?"),      # no I-word: it asks about us
    ("22", "how do I pay?"),        # 2 of 4 words in the question
    ("01", "what should I say?"),
    ("01", "what do you mean?"),    # their own "you": about us
    ("04", "why?"),                 # one word is too few to tell
    ("03", "what what?"),           # "what?" alone is never their words
    ("m_open_wallet", "can we do option 2?"),  # its words are in the talk, not the question
])
def test_a_question_of_their_own_is_not_the_question_said_back(seller, step, said):
    assert not seller._ear._asked_back(said, ScriptState(step=step))
