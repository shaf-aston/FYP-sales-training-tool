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
    ("credit, is that ok?", "credit", ""),   # round 25 replay: a check-in tag is talk, not a question
    ("is that ok?", "", ""),
    ("it's 2.5k, is that a lot?", "it's 2.5k", "is that a lot?"),   # "2.5k" is never cut at its point
    ("3k, no wait, more like 4k", "more like 4k", ""),   # whole calls: the 3k they took back was kept
    ("3 years, sorry, 2 years", "2 years", ""),
    ("pay off my car, no actually my credit card", "my credit card", ""),
    ("sorry, where were we?", "", "where were we?"),   # was "sorry" taken as their answer
    ("wait, sorry, what's this going to cost me?", "", "what's this going to cost me?"),   # one after another
    ("nothing, sorry", "nothing", ""),   # nothing after it: nothing taken back, and a lone "sorry" beside it is a hedge
    ("yes, sorry", "yes", ""),   # round 24: "yes, sorry" at the close was heard as unsure
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
    ("I was wondering how this works first", "", "I was wondering how this works first"),   # round 24: heard as unclear; all asked: as typed
    ("about 2k, I was wondering what it costs", "about 2k", "what it costs?"),   # a polite lead asks in any part
    ("I'd like to know the price first", "", "I'd like to know the price first"),
    ("I was wondering", "I was wondering", ""),   # a lead with nothing after it asks nothing
    ("is it ok to say quit my job?", "quit my job", ""),   # round 24: the answer, its "?" asks leave
    ("would it be ok if I said 2 years?", "2 years", ""),
    ("is it ok to say quit?", "quit my job", ""),   # round 49 callers: bare "quit" after the lead ended the call
    ("I'd say quit", "quit my job", ""),
    ("is it ok to say?", "", "is it ok to say?"),   # nothing after the lead: a question, as typed
    ("I told you, my job", "my job", ""),   # round 37 callers: heard as "what do you mean?", the job lost
    ("I already told you 2k", "2k", ""),
    ("I told you already", "I told you already", ""),   # a lead with nothing after it is the reply
    ("I just told you", "I just told you", ""),
    ("sorry for the long message, I want to quit my job", "I want to quit my job", ""),   # round 24: an aside
    ("yes, lol", "yes", ""),   # a part of only no-answer words beside others is a hedge
    ("sorry", "sorry", ""),   # on its own it is the reply, never a hedge left out
    ("3k, actually make it 5k", "5k", ""),   # round 25: the 3k was kept
    ("more money, actually no, more time", "more time", ""),   # round 25: said back whole
    ("actually no idea", "actually no idea", ""),   # "actually no" takes back only with a break after it
    ("a million, jk, 2k", "2k", ""),   # round 26 callers: "jk" between two answers takes the first back
    ("buy a yacht obviously, lol no, pay rent", "pay rent", ""),
    ("jk lol", "jk", ""),   # with nothing after it, nothing is taken back ("lol" at the end is its own part, as in "jk, lol")
    ("I guess my car loan?", "I guess my car loan", ""),   # round 26 callers: unsure, not asking ("I'll find out")
    ("lol, probably like 2k?", "probably like 2k", ""),
    ("maybe a year?", "maybe a year", ""),
    ("is it a year?", "", "is it a year?"),   # a question still asks
    ("well, to be honest with you, more money", "more money", ""),   # round 27 callers: was said back whole
    ("more money, well, more time really", "more time really", ""),   # "well" with a break takes back
    ("uh pay rent and stuff you know", "uh pay rent", ""),   # round 27 callers: "and stuff you know" is talk
    ("uh pay rent, stuff you know", "uh pay rent", ""),   # "stuff you know" is talk
    ("to be fair, around 2k", "around 2k", ""),
    ("well I want more money", "well I want more money", ""),   # guard: "well" with no break is a word
    ("yeah no, not for me", "no, not for me", ""),   # round 28 callers: a yes and no said together mean the last one
    ("yeah no, I mean yes", "yes", ""),
    ("no yeah, it makes sense", "it makes sense", ""),   # was heard as backing out
    ("yeah no worries", "yeah no worries", ""),   # guard: no break after the "no", it is a phrase
    ("what happens next?", "", "what happens next?"),   # round 31: "next" was cut off and "what happens" said back
    ("I want to carry on", "I want to carry on", ""),
    ("debit, next", "debit", ""),   # guard: after a break it still nudges
    ("about 2k a month, if that helps", "about 2k a month", ""),   # round 32: "if that helps" got "You're welcome."
    ("2k, no 3k", "3k", ""),   # round 33: a correction between two amounts needs no break after it (the 2k was kept)
    ("a year, well two", "two year", ""),   # a bare amount keeps the unit said with the first (was "12 months")
    ("about a year, no 2", "2 year", ""),
    ("6 months, no a year", "a year", ""),
    ("pay off debt, well 5k of it", "pay off debt, well 5k of it", ""),   # guard: no amount before, nothing taken back
    ("a year, no more", "a year, no more", ""),   # guard: no amount after
    ("6 months, actually more like a year", "more like a year", ""),   # round 34: a span fixed by a span (was both)
    ("more time, sorry more money", "more money", ""),   # two answers that start the same: the second is meant
    ("quit my job, actually quit my job and travel", "quit my job and travel", ""),
    ("yes, sorry the baby was crying", "yes, sorry the baby was crying", ""),   # guard: two kinds, nothing taken back
    ("a year, sorry had to pay for parking", "a year, sorry had to pay for parking", ""),   # guard: no span after
    ("to be completely honest, more money", "more money", ""),   # round 41: said back as "by being completely honest, more money"
    ("if I really think about it, about a year", "about a year", ""),   # round 41: heard as "I need to think about it"
    ("at the end of the day, being my own boss", "being my own boss", ""),
    ("realistically speaking, about 2k a month", "about 2k a month", ""),
    ("I really think about it a lot", "I really think about it a lot", ""),   # guard: no break, it is what they said
    ("yes sorry", "yes", ""),   # round 39: an end word that answers nothing is its own part, as "yes, sorry" (was unclear)
    ("more money lol", "more money", ""),
    ("sorry I was driving", "sorry I was driving", ""),   # guard: only at the end
    ("lol", "lol", ""),   # guard: alone it is the reply
    ("money I guess", "money", ""),   # round 44 callers: a hedge at the end is its own part (got "What do you mean by money?")
    ("no idea, money I guess", "no idea, money", ""),
    ("yeah I guess", "yeah I guess", ""),   # guard: only after real words
    ("I guess", "I guess", ""),
])
def test_a_reply_is_read_once_into_what_it_says_and_what_it_asks(text, said, asked):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    reply = Reader(CFG, load_common_sense().nudges, lambda part: part.lower() in HEDGES).read(text)
    reply = reply.settle(lambda part: False)
    assert (reply.said, reply.asked) == (said, asked)


@pytest.mark.parametrize("text, asked", [("about 2k, I was wondering what it costs ?", "what it costs?"),
                                          ("about 2k, I'd like to know the price", "the price?")])
def test_a_polite_lead_asks_even_when_a_rise_would_be_heard_as_an_answer(text, asked):
    """Round 24: the part after "I was wondering" is a question, never settled into content ("what it costs?")."""
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    reply = Reader(CFG, load_common_sense().nudges, lambda part: part.lower() in HEDGES).read(text)
    reply = reply.settle(lambda part: True)
    assert (reply.said, reply.asked) == ("about 2k", asked)


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


@pytest.mark.parametrize("said, after, line", [
    ("I had to go, talk later", "02", "If you had to put a number on it"),   # round 33 callers: a goodbye in the past ended the call
    ("I have to go now", "later", None),   # guard: still leaving
    ("sorry, my kid is yelling", "02", "No problem, take your time."),   # guard: a pause now still waits
])
def test_a_pause_said_in_the_past_is_over(seller, said, after, line):
    text, _ = at(seller, "02").reply(said)
    assert seller.state.step == after, text
    assert not line or text.startswith(line), text


@pytest.mark.parametrize("text, name, over", [
    ("sorry kids were shouting", "pause", True),   # round 33 callers: "sorry kids were shouting, 2k" got "take your time"
    ("sorry was driving", "leaving", True),   # "sorry was driving, 2k" ended the call
    ("sorry, my kid is yelling", "pause", False),
    ("thanks, that was helpful", "thanks", False),   # only a pause or goodbye can be over
])
def test_a_pause_or_goodbye_in_the_past_is_over(seller, text, name, over):
    assert seller._ear._over(text, name) == over


@pytest.mark.parametrize("question, examples, names", [
    ("which is better?", ["whichever is easier", "either is fine"], False),   # round 34: asks advice, chooses nothing
    ("can I use paypal?", ["paypal", "credit"], True),
    ("debit card is ok?", ["debit card please"], True),
    ("is it?", ["credit"], True),   # only small words: the score alone decides, as before
])
def test_a_question_chooses_an_answer_only_when_it_names_one_of_its_words(seller, question, examples, names):
    assert seller._ear._names(question, examples) == names


@pytest.mark.parametrize("text, kept", [
    ("sorry, I was away for a minute, more money", "more money"),   # round 34 callers: the whole was saved
    ("more money, sorry, I was away for a minute", "more money"),   # the lone "sorry" beside it answers nothing: cut too
    ("sorry I was away for a minute, more money", "more money"),   # the break is one part
    ("sorry I was away for a minute, more money, more time", "more money, more time"),   # the fewest parts: the answer stays
    ("more money, more time, sorry, I was away for a minute", "more money, more time"),
    ("sorry, my kid is yelling, more money", "sorry, my kid is yelling, more money"),   # guard: a pause now is no aside
    ("I was broke, more money", "I was broke, more money"),   # guard: the past, but no break
    ("sorry, I was away for a minute, ok, more money", "more money"),   # the "ok" between answers nothing: cut
    ("more money, ok, sorry, I was away for a minute", "more money"),
    ("sorry, I was away for a minute, ok", "ok"),   # the last part left is kept, even if it answers nothing
])
def test_a_break_that_is_over_is_cut_from_the_answer(seller, text, kept):
    at(seller, "01")
    assert seller._ear._unbroken(text, seller.method.steps["01"], seller.state) == kept


@pytest.mark.parametrize("found, question, answers", [
    (("pays", False), "which is better?", False),   # sure, but names no word of the answer: it asks
    (("pays", False), "can I use paypal?", True),
    (("pays", True), "which is better?", True),   # torn between two answers is still answering
    ((None, False), "which is better?", True),   # no one answer to check it against: the score decides
])
def test_a_sure_question_answers_only_when_it_names_the_answer(seller, monkeypatch, found, question, answers):
    from types import SimpleNamespace
    ear, step = seller._ear, seller.method.steps["22"]
    monkeypatch.setattr(ear._listener, "answer_score", lambda *a, **k: 0.81)
    monkeypatch.setattr(ear._listener, "match", lambda *a, **k: SimpleNamespace(label=found[0], close=found[1],
                                                                       score=ear.cfg["question_answer_min_score"]))   # just sure
    assert ear._answers(question, step) == answers
    assert ear._chooses(question, step) == (found[0] if answers and not found[1] and found[0] else "")


def test_a_question_less_than_sure_is_no_answer(seller):
    assert not seller._ear._answers("what happens to the card?", seller.method.steps["22"])   # asks about the card
    assert not seller._ear._answers("what card?", seller.method.steps["22"])   # 0.71 to "card": near, not sure


def test_which_is_better_at_payment_is_no_way_to_pay(seller):
    said, _ = at(seller, "22").reply("which is better?")   # round 34 callers: got "Welcome aboard"
    assert seller.state.step == "22" and said.startswith("There's no right answer")


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
    ("my job?", True), ("my kids?", True),               # round 28 callers: their own thing said with a rise was "I'll find out"
    ("what job?", False),                                # guard: a question word still asks
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
    assert seller._ear._correction("sorry I meant 3k", ScriptState(step="02", slots={"number": "2k"})) == (None, "")
    assert seller._ear._correction("sorry I meant 3k", ScriptState(step="03", slots={"number": "2k"}))[0].text == "3k"


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


@pytest.mark.parametrize("said", ["what?", "what", "eh?", "sorry, what?", "pardon?", "wait what?"])
def test_what_alone_wants_the_question_put_another_way(seller, said):
    """Round 21: "what?" was torn between "say that again" and "why do you ask", and got "I'll find out"."""
    v = at(seller, "03")._ear.hear(said, seller.state, False)
    assert (v.kind, v.name) == ("sense", "clarify"), v


@pytest.mark.parametrize("said", ["what do most people make?", "sorry", "what's next?", "what about you?"])
def test_a_question_with_what_in_it_is_not_what_alone(seller, said):
    assert not seller._ear._what_alone(said)


@pytest.mark.parametrize("step, said", [
    ("02", "a month?"),        # "...making each month..."
    ("02", "months?"),         # a plural of the question's word
    ("01", "achieve?"),
    ("19", "jumping in?"),
    ("02", "each month? "),     # two words, a space after the "?"
    ("belief_cost", "year?"),  # "...over the next few years?"
    ("02", "per month?"),      # round 40: got the payment plan line
    ("02", "monthly?"),        # round 40: "-ly" on the question's word
])
def test_a_word_from_the_question_said_back_wants_it_put_another_way(seller, step, said):
    """Round 23: "a month?" to "How much... each month...?" got "I'll find out"; "achieve?" got the AI line."""
    assert seller._ear._word_back(said, ScriptState(step=step))
    v = at(seller, step)._ear.hear(said, seller.state, False)
    assert (v.kind, v.name) == ("sense", "clarify"), v


@pytest.mark.parametrize("step, said", [
    ("02", "a month"),          # no "?": said, not asked
    ("22", "debit?"),           # the question offers a choice: it picks one
    ("04", "why?"),             # a question word asks
    ("02", "2k?"),              # not the question's words
    ("01", "achieve more money?"),   # 3 words is too many: their own question
    ("02", "need to be making each month?"),    # 3 words ("each" skipped): their own question, not a word said back
    ("02", "?"),                # no words at all
    ("02", "bills?"),           # ends in "s", but "bill" isn't in the question either
    ("14", "a month?"),         # round 40: the price line asks nothing, so "a month?" asks how it is paid
    ("02", "only?"),            # "-ly" alone lifts nothing
])
def test_a_reply_of_its_own_is_not_a_word_said_back(seller, step, said):
    assert not seller._ear._word_back(said, ScriptState(step=step))


@pytest.mark.parametrize("step, text, acts", [
    ("03", "how long? about 2 years", ["tag", "said"]),     # was heard as "recent": "how long?" is near "not long"
    ("goal_practical", "achieve? quit my job", ["tag", "said"]),   # was "What do you mean by achieve?"
    ("01", "what do I want? more money", ["tag", "said"]),  # their I-words are our you-words
    ("02", "how much? about 2k", ["tag", "said"]),
    ("03", "how long?", ["asks"]),                         # said back alone: it still asks for it another way
    ("02", "how much is it? about 2k", ["asks", "said"]),  # their own question, not ours said back
    ("02", "about 2k, how much?", ["said", "asks"]),       # only before the answer
    ("03", "how long? how long? 2 years", ["tag", "tag", "said"]),
    ("02", "how much? is it before tax?", ["tag", "asks"]),   # their own question after it still asks ("is it monthly?" is ours said back: round 40)
    ("03", "how long? a year?", ["tag", "asks"]),          # and an answer with a rise is settled later
    ("01", "what am I hoping to achieve? more money", ["tag", "said"]),   # round 31: 4 of 6 words got "I'm the AI"
])
def test_the_question_said_back_before_an_answer_is_talk(seller, step, text, acts):
    """Round 26 callers: "how long? about 2 years" went to "So what made it come up for you now?"."""
    read = seller._ear.reader.read(text)
    reply = seller._ear._unecho(read, ScriptState(step=step))
    assert [p.act if p.act != "rise" else "asks" for p in reply.parts] == acts
    assert [p.text for p in reply.parts] == [p.text for p in read.parts]   # only the act changes


@pytest.mark.parametrize("name, spoken, again", [
    ("thanks", ("You're welcome.",), True),   # round 27 callers: "ok, thank you" a second time was "What do you mean by thank you?"
    ("thanks", (), False),                    # the first thank-you is answered
    ("thanks", ("Fair enough.",), False),     # another line said is not this one
])
def test_a_remark_answered_once_is_heard_as_the_rest(seller, name, spoken, again):
    assert seller._ear._said_again(name, ScriptState(step="05", spoken=spoken)) is again


@pytest.mark.parametrize("name", ["repeat", "back", "clarify", "why_ask"])
def test_only_a_once_remark_is_heard_as_the_rest(seller, name):
    """"say what now?" twice asks twice (round 27: Eli's second one was missed); "ok, I'm back" follows a new pause."""
    said = seller._ear.sense.interruptions[name].reply
    assert not seller._ear._said_again(name, ScriptState(step="05", spoken=(said,)))


def test_a_later_answer_in_one_part_is_kept_and_left_out_of_this_one(seller):
    """Round 27 callers: "more money, about 2k a month" had "about 2k a month" said back, and the income asked again."""
    ahead, text = seller._ear._ahead("more money, about 2k a month", seller.method.steps["01"], ScriptState(step="01"))
    assert ahead is not None and ahead.slots.get("number"), ahead
    assert text == "more money"
    ahead, text = seller._ear._ahead("more money", seller.method.steps["01"], ScriptState(step="01"))
    assert ahead is None and text == "more money"


@pytest.mark.parametrize("text, parts", [
    ("more money,more time", ["more money", "more time"]),   # round 28 callers: a comma with no space was one part
    ("2k,maybe 3k", ["2k", "maybe 3k"]),
    ("5,000 a month", ["5,000 a month"]),   # guard: a comma inside a number is not a break
    ("1,5k", ["1,5k"]),
])
def test_a_comma_with_no_space_breaks_but_never_inside_a_number(text, parts):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    reply = Reader(CFG, load_common_sense().nudges, lambda part: False).read(text)
    assert [p.text for p in reply.parts] == parts


@pytest.mark.parametrize("text, parts", [
    ("yeah. quit.", [("yeah", "tag"), ("quit my job", "said")]),   # round 47 callers: "quit" next to another part ended the call
    ("quit lol", [("quit my job", "said"), ("lol", "hedge")]),
    ("what would I do? quit", [("what would I do?", "asks"), ("quit my job", "said")]),   # round 45 callers
    ("what? y", [("what?", "asks"), ("yes", "said")]),
    ("quit? no", [("quit?", "rise"), ("no", "said")]),   # guard: only a part said, never one asked
    ("quit", [("quit", "said")]),                         # guard: alone it is still leaving
])
def test_a_short_form_next_to_another_part_is_its_word(text, parts):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    reply = Reader(CFG, load_common_sense().nudges, lambda part: False).read(text)
    assert [(p.text, p.act) for p in reply.parts] == parts


@pytest.mark.parametrize("text, parts", [
    ("yeah, ok", [("yeah", "said"), ("ok", "said")]),   # round 47 callers: "yeah" was left out, so "ok" alone was unclear
    ("yeah. ok.", [("yeah", "said"), ("ok", "said")]),
    ("yeah, my boss", [("yeah", "tag"), ("my boss", "said")]),   # guard: beside content it is still talk
])
def test_a_tag_with_no_content_beside_it_is_the_reply(text, parts):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    reply = Reader(CFG, load_common_sense().nudges, lambda part: False).read(text)
    assert [(p.text, p.act) for p in reply.parts] == parts


@pytest.mark.parametrize("text, said", [
    ("maybe money?", "maybe money"),   # round 48 callers: a "?" on a guess was asked "What do you mean by money?"
    ("maybe money? or time?", "maybe money"),   # guard: parts left out are joined as before
    ("what's money?", ""),   # guard: a question is still asked, never said
])
def test_a_question_mark_on_a_said_reply_is_not_kept(text, said):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    assert Reader(CFG, load_common_sense().nudges, lambda part: False).read(text).said == said


def test_a_question_beside_what_they_said_keeps_its_question_mark():
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    assert Reader(CFG, load_common_sense().nudges, lambda part: False).read("money, why?").meant == "money, why?"   # guard: round 48


@pytest.mark.parametrize("text, meant", [
    ("quit, obviously, like everyone", "quit my job, obviously"),   # round 47 callers: heard as who they want to be
    ("I don't want to be like everyone else", "I don't want to be like everyone else"),   # guard: inside the part it is theirs
])
def test_like_everyone_after_the_answer_is_a_tag(text, meant):
    from core.buy_mode.script_engine.hear.reply import Reader
    from core.buy_mode.script_engine.method import load_common_sense
    assert Reader(CFG, load_common_sense().nudges, lambda part: False).read(text).meant == meant


@pytest.mark.parametrize("said, step, slots", [
    ("no wait, I meant 3k, and a year", "04", {"number": "3k", "years": "and a year"}),   # round 29 callers: "a year" was lost, 03 asked again
    ("sorry I meant 3k not 2k", "03", {"number": "3k"}),   # guard: a fix alone asks the step again
])
def test_a_fix_with_this_steps_answer_after_it_keeps_both(seller, said, step, slots):
    at(seller, "03", number="2k").reply(said)
    assert (seller.state.step, seller.state.slots) == (step, slots), seller.last_turn


@pytest.mark.parametrize("step, said, after", [
    ("05", "no thank you", "later"),   # round 34 callers: kept as the answer, 25 steps on
    ("goal_practical", "I'm not interested", "later"),
    ("willing", "no thank you", "11"),   # to a yes-or-no question it is a plain no
    ("17", "no thanks", "18"),   # `yes_no`: "Open to being called out?" wants a yes or no
])
def test_a_polite_no_before_the_price_leaves_the_call(seller, step, said, after):
    at(seller, step).reply(said)
    assert seller.state.step == after


def test_a_polite_no_at_the_close_is_the_closes_own(seller):
    at(seller, "20").reply("no thank you")   # `before_price`: the close's routes hear it (backs out, the soft close)
    assert seller.state.step != "later"


def test_thanks_beside_a_no_keeps_it_a_plain_no_only_to_a_yes_or_no_question(seller):
    shrugs = seller._ear._shrugs
    assert shrugs.plain_no("no thank you", True) and shrugs.plain_no("nah, thanks", True)
    assert not shrugs.plain_no("no thank you", False)   # to an open question: no to the call
    assert not shrugs.plain_no("no thanks, I have a job", True)   # more than a no
    assert not shrugs.plain_no("thanks", True)   # no no in it


def test_a_step_can_want_a_yes_or_no_with_no_helper_verb(seller):
    at(seller, "17")
    assert seller.method.steps["17"].yes_no and seller._ear._yes_or_no(seller.state)
    at(seller, "05")
    assert not seller._ear._yes_or_no(seller.state)


@pytest.mark.parametrize("said, nothing", [
    ("because", True),   # round 34 callers: saved as the answer at every open step
    ("cos", True),
    ("because I hate my job", False),   # guard: a reason
])
def test_because_alone_says_nothing(seller, said, nothing):
    assert seller._ear._shrugs.says_nothing(said, seller.method.steps["05"], False) == nothing


@pytest.mark.parametrize("said, means", [
    ("what do you mean stopping me?", True),   # round 40: got "I'll find out"
    ("wdym by that?", True),                   # "wdym" reads "what do you mean"
    ("what does that mean?", True),
    ("what do you do?", False),                # guard: a question about us
    ("what does mentorship mean?", False),     # guard: a product question names its thing
])
def test_a_question_asking_what_we_meant_opens_with_it(seller, said, means):
    from core.buy_mode.script_engine.words.fill import fix_typos
    assert seller._ear._means_what(fix_typos(said, frozenset(), seller.cfg)) is means


def test_an_unknown_question_asking_what_we_meant_is_put_another_way(seller):
    """Round 40 callers: "what do you mean stopping me?" to 04 got "I don't know that one offhand"."""
    v = at(seller, "04")._ear.hear("what do you mean stopping me?", seller.state, False)
    assert (v.kind, v.name) == ("sense", "clarify"), v
