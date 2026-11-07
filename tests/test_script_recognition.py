"""The real embedder against the public labelled replies. Opt-in (downloads a model)."""
import os
import statistics
import time
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from core.buy_mode.script_engine.hear.embedder import make_embedder
from core.buy_mode.script_engine.hear.recognise import Listener
from core.buy_mode.script_engine.method import (
    load_common_sense,
    load_method,
    load_offer,
)
from core.infra.loader import load_yaml

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EMBED_TESTS") != "1", reason="set RUN_EMBED_TESTS=1 (downloads a model)"
)

ROOT = Path(__file__).parent.parent
MIN_ACCURACY = 0.85
MIN_OFF_TOPIC = 0.80
MAX_CONFIDENT_WRONG = 0.03
MAX_MEDIAN_MS = 50


def _step_labels(method, step_id):
    return {r.label: list(r.examples) for r in method.steps[step_id].listen if r.examples}


def _objection_labels(method):
    return {k: list(o.examples) for k, o in method.objections.items()}


def _contexts():
    cat, impact = load_method("cat"), load_method("impact_formula")
    return {
        "step_01": _step_labels(cat, "01"),
        "step_18": _step_labels(cat, "18"),
        "step_19": _step_labels(cat, "19"),
        "step_22": _step_labels(cat, "22"),
        "objections_cat": _objection_labels(cat),
        "objections_impact": _objection_labels(impact),
        "facts": {k: list(f.examples) for k, f in load_offer("shay_coaching").facts.items()},
        "common_sense": {
            k: list(i.examples) for k, i in load_common_sense().interruptions.items() if not i.after_wait  # as heard mid-step
        },
    }


@pytest.fixture(scope="module")
def results():
    cfg = load_yaml("script/engine.yaml")
    embedder = make_embedder(cfg, ROOT)
    listener = Listener(cfg, embedder)
    floors = {k: i.min_score for k, i in load_common_sense().interruptions.items()}  # as the seller judges them
    data = yaml.safe_load((ROOT / "tests/data/script_replies.yaml").read_text(encoding="utf-8"))
    embedder.warm([e for labels in _contexts().values() for ex in labels.values() for e in ex])
    rows, times = [], []
    for context, labels in _contexts().items():
        for expected, replies in data[context].items():
            for reply in replies:
                start = time.perf_counter()
                match = listener.match(reply, labels)
                if context == "common_sense" and match.label and match.score < floors[match.label]:
                    match = replace(match, label=None)
                times.append((time.perf_counter() - start) * 1000)
                rows.append((context, reply, expected, match))
    return rows, times


def _got(match):
    return match.label or "none"


def test_labelled_set_is_big_enough(results):
    assert len(results[0]) >= 150


def test_accuracy_off_topic_and_confident_wrong(results, capsys):
    rows, _ = results
    on = [r for r in rows if r[2] != "none"]
    off = [r for r in rows if r[2] == "none"]
    strict = sum(_got(m) == exp and not m.close for _, _, exp, m in on)
    close = sum(m.close for _, _, _, m in rows)
    wrong = [(c, r, e, _got(m)) for c, r, e, m in rows if _got(m) != e and not m.close]
    flagged = sum(m.label is None or m.close for _, _, _, m in off)
    with capsys.disabled():
        print(f"\nrows {len(rows)}  strict top-1 {strict}/{len(on)} = {strict / len(on):.1%}"
              f"  close-call rate {close}/{len(rows)} = {close / len(rows):.1%}"
              f"  confident-wrong {len(wrong)}/{len(rows)} = {len(wrong) / len(rows):.1%}"
              f"  off-topic flagged {flagged}/{len(off)}")
        for w in wrong:
            print("  WRONG", w)
    assert strict / len(on) >= MIN_ACCURACY
    assert len(wrong) / len(rows) <= MAX_CONFIDENT_WRONG
    assert flagged / len(off) >= MIN_OFF_TOPIC


@pytest.mark.parametrize("context, negated", [("step_18", "unclear"), ("step_19", "hesitant")])
def test_negations_never_confidently_wrong(results, context, negated):
    rows = [r for r in results[0] if r[0] == context and r[2] == negated]
    assert len(rows) >= 10
    for _, reply, _, match in rows:
        assert match.label == negated or match.close or match.label is None, (reply, match)
        assert match.label != "agrees", (reply, match)


def test_latency(results, capsys):
    median = statistics.median(results[1])
    with capsys.disabled():
        print(f"\nmedian recognise {median:.1f} ms")
    assert median <= MAX_MEDIAN_MS


def test_combined_interruption_set_picks_the_right_group(capsys):
    """The seller matches interruptions, facts and objections in one pass: groups must not steal."""
    cfg = load_yaml("script/engine.yaml")
    embedder = make_embedder(cfg, ROOT)
    listener = Listener(cfg, embedder)
    ctxs = _contexts()
    embedder.warm([e for labels in ctxs.values() for ex in labels.values() for e in ex])
    labels = {}
    for group, key in (("sense", "common_sense"), ("fact", "facts"), ("objection", "objections_cat")):
        labels.update({f"{group}:{k}": v for k, v in ctxs[key].items()})
    data = yaml.safe_load((ROOT / "tests/data/script_replies.yaml").read_text(encoding="utf-8"))
    rows = [
        (f"{group}:{label}", reply)
        for group, key in (("sense", "common_sense"), ("fact", "facts"), ("objection", "objections_cat"))
        for label, replies in data[key].items() if label != "none"
        for reply in replies
    ]
    hits = 0
    for expected, reply in rows:
        m = listener.match(reply, labels)
        hits += m.label == expected or m.close
        if m.label != expected and not m.close:
            with capsys.disabled():
                print("  MIXED UP", reply, "->", m.label, "expected", expected)
    with capsys.disabled():
        print(f"\ncombined {hits}/{len(rows)}")
    assert hits / len(rows) >= MIN_ACCURACY


def test_only_script_examples_are_remembered_never_replies():
    embedder = make_embedder(load_yaml("script/engine.yaml"), ROOT)
    embedder.warm(["I want freedom"])
    embedder.embed(["I want freedom", "a prospect reply nobody will ever warm"])
    assert list(embedder._seen) == ["I want freedom"]


def _down(prompt, max_tokens):
    raise RuntimeError("AI down")


@pytest.mark.parametrize("replies, expected_step", [
    # plain answers to the step's own question: never an interruption or a product question
    # (step 01 is a goal ladder: level 1, then level 2, then level 3, then 02)
    (["I just want freedom, to stop working for someone else and travel", "so I can stop worrying about bills", "I'd finally be proud of myself", "maybe 8k a month"], "03"),
    (["I want freedom", "so I can stop worrying about bills", "I'd finally be proud of myself", "10k a month", "about two years now"], "04"),
    (["I want freedom", "so I can stop worrying about bills", "I'd finally be proud of myself", "10k a month", "two years", "because I hate missing time with my kids"], "05"),
    (["I want freedom", "so I can stop worrying about bills", "I'd finally be proud of myself", "ok cool, about 10k", "three years"], "04"),
])
def test_answers_move_the_script_on(replies, expected_step):
    from core.buy_mode.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    for text in replies:
        seller.reply(text)
    assert seller.state.step == expected_step


def test_real_price_question_still_gets_the_early_answer():
    from core.buy_mode.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    seller.reply("I want freedom")
    text, _ = seller.reply("wait, sorry, what's this going to cost me?")
    early = (seller.offer.facts["price"].answer, seller.method.objections["money"].early)
    assert text.startswith(early) and seller.state.step == "goal_practical"


def _real_seller():
    from core.buy_mode.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    return ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                        make_embedder(cfg, ROOT), _down)


@pytest.mark.parametrize("said", ["money is tight and I don't have time", "I'm scared it won't work for me"])
def test_open_question_takes_an_objection_shaped_reply_as_its_answer(said):
    # "What's the reason you haven't got there?" - "money is tight" IS the answer, not an objection
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="05", slots={"outcome": "financial freedom"}))
    text, _ = seller.reply(said)
    assert seller.sense.park not in text and seller.state.step != "05"


@pytest.mark.parametrize("said", ["I want more time with my kids", "to spend time with my family"])
def test_family_time_goal_is_an_answer_not_a_pause(said):
    # a level 2 goal: skips the formula, straight to the identity rung
    seller = _real_seller()
    text, _ = seller.reply(said)
    assert seller.state.step == "goal_identity" and "take your time" not in text


@pytest.mark.parametrize("said", ["this sounds like a scam honestly", "I need to talk to my wife first",
                                  "I can't afford it right now"])
def test_objection_mid_discovery_is_acknowledged(said):
    seller = _real_seller()
    seller.reply("I want financial freedom")
    text, _ = seller.reply(said)
    names = {"this sounds like a scam honestly": "scam", "I need to talk to my wife first": "partner",
             "I can't afford it right now": "money"}
    expected = seller.method.objections[names[said]].early or seller.sense.park
    assert text.startswith(expected) and seller.state.step == "goal_practical" and names[said] in seller.state.parked


@pytest.mark.parametrize("step", ["01", "05", "09"])
@pytest.mark.parametrize("said", ["isnt this just a scam", "is this legit", "have you got any proof", "how do I know it works"])
def test_a_trust_question_gets_the_early_line_even_without_a_question_mark(step, said):
    # step 05 takes money, time and fear as its answer; a trust question is still asked, not answered
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step=step))
    text, _ = seller.reply(said)
    assert text.startswith(seller.method.objections["scam"].early) and seller.state.step == step


@pytest.mark.parametrize("said", ["this is taking too long", "can we hurry up"])
def test_hurrying_the_call_up_is_frustration_not_a_pause(said):
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="05"))
    assert seller.reply(said)[0].startswith(seller.sense.interruptions["frustrated"].reply)


@pytest.mark.parametrize("step", ["03", "04", "05", "18"])
def test_a_pause_is_a_pause_on_any_step(step):
    from core.buy_mode.script_engine.engine import ScriptState
    from core.buy_mode.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    seller.reset(ScriptState(step=step))
    assert seller.reply("sorry hold on, my kid is yelling")[0] == "No problem, take your time."
    assert seller.state.step == step


def test_vague_opening_answer_gets_a_dig_not_an_objection_line():
    seller = _real_seller()
    text, _ = seller.reply("I want to make money online")
    assert seller.sense.park not in text and seller.state.step == "01"


@pytest.mark.parametrize("reply", ["I'm not paying you anything", "you're not getting my money"])
def test_refusing_to_pay_at_the_start_is_the_money_worry_not_a_goal(reply):
    seller = _real_seller()
    text, _ = seller.reply(reply)  # live: "I'm not giving you money" was dug into as their goal
    assert text.startswith(seller.method.objections["money"].early) and seller.state.step == "01"
    assert "outcome" not in seller.state.slots


def test_failed_past_attempt_gets_an_acknowledgement():
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="03"))
    text, _ = seller.reply("I tried dropshipping and it failed")
    assert text.startswith("Sorry to hear that") and seller.state.step == "03"  # still asked how long
    assert "years" not in seller.state.slots


def test_floored_labels_clear_their_floor_only_when_meant(capsys):
    """Keen buyer and frustration act on one message, so each has its own floor: real replies must
    clear it when meant and never when not (heard as the seller hears them at step 01)."""
    cfg = load_yaml("script/engine.yaml")
    embedder = make_embedder(cfg, ROOT)
    listener = Listener(cfg, embedder)
    cat, sense = load_method("cat"), load_common_sense()
    labels = {**_step_labels(cat, "01"), "ready": list(cat.ready.examples)}
    labels.update({k: list(i.examples) for k, i in sense.interruptions.items() if not i.after_wait})
    floors = {"ready": cat.ready.min_score, **{k: i.min_score for k, i in sense.interruptions.items()}}
    data = yaml.safe_load((ROOT / "tests/data/script_replies.yaml").read_text(encoding="utf-8"))["floored"]
    embedder.warm([e for ex in labels.values() for e in ex])
    for label, rows in data.items():
        def fires(reply, label=label):
            m = listener.match(reply, labels)
            return m.label == label and not m.close and m.score > floors[label]

        hit = [r for r in rows["meant"] if fires(r)]
        false = [r for r in rows["not_meant"] if fires(r)]
        with capsys.disabled():
            print(f"\n{label}: meant {len(hit)}/{len(rows['meant'])}  false {false}")
        assert not false
        assert len(hit) / len(rows["meant"]) >= MIN_OFF_TOPIC


@pytest.mark.parametrize("reply, heard", [
    ("money", "answer"),        # live: got "I haven't mentioned a price yet"
    ("scared", "answer"),       # live: parked as a fear objection
    ("risk I guess", "answer"),
    ("I can't afford anything right now", "objection:money"),
    ("I'm scared it won't work for me", "objection:fear"),
    ("I just want to know the price", "fact:price"),   # live: "I haven't mentioned a price yet" answered a price request
])
def test_before_the_price_short_answers_are_not_objections(reply, heard):
    from core.buy_mode.script_engine import seller as S
    gate = type("Down", (), {"llm": lambda self, router: None})()
    real = make_embedder(load_yaml("script/engine.yaml"), ROOT)  # not S.shared_embedder: conftest swaps in the fake
    s = S.build_seller(None, S.resolve_product(None), embedder=real, gate=gate)
    s.opening()
    s.reply(reply)
    assert s.last_turn["heard_as"].startswith(heard)


# Live shrugs must count as unclear; real short answers (some hedged) must not. Measured on the model.
SHRUGS = ["dunno man", "stuff i guess", "nah not sure", "i dont really know", "no clue lol", "not sure tbh",
          "idk really", "depends", "hmm let me think", "eh", "good question", "maybe", "who knows", "umm"]
ANSWERS = ["nothing yet", "nothing, I just watch youtube", "maybe travel", "maybe 5k", "idk maybe 5k",
           "dunno, a couple of years", "good question, freedom probably", "let me think, probably my kids",
           "I don't know if I can afford it", "I don't know where to start", "honestly I don't know what's stopping me",
           "no time", "money is tight", "still researching", "2 years", "freedom", "5k a month", "my kids",
           "whatever pays the bills", "eh, freedom I guess"]


def test_shrugs_are_unclear_and_real_answers_are_not():
    sense = load_common_sense()
    listener = Listener(load_yaml("script/engine.yaml"), make_embedder(load_yaml("script/engine.yaml"), ROOT))
    score = {t: listener.match(t, {"unclear": list(sense.unclear)}, by_clause=False).score for t in SHRUGS + ANSWERS}  # as shrug.py hears it
    assert [t for t in SHRUGS if score[t] < sense.unclear_min_score] == []
    assert [t for t in ANSWERS if score[t] >= sense.unclear_min_score] == []


@pytest.mark.parametrize("said, step", [("what happens to the card exactly?", "m_open_wallet"), ("can we do option 2?", "22")])
def test_a_card_question_asks_and_a_sure_choice_chooses(said, step):
    # at the wallet: asking about the card is not choosing to pay, "can we do option 2?" is
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="m_open_wallet"))
    seller.reply(said)
    assert seller.state.step == step


def test_a_scam_question_where_doubts_are_answers_is_the_scam_worry_not_a_bot_question():
    # live call: "is this a scam though?" at "what's stopping you" got "Yes, I'm an AI..."
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    step = next(k for k, s in seller.method.steps.items() if s.doubts_answer)
    seller.reset(ScriptState(step=step))
    reply, _ = seller.reply("is this a scam though?")
    assert "I'm an AI" not in reply


@pytest.mark.parametrize("said, clarify", [
    ("I don't know, enough to live", False),  # live: "Fair point, let me put it another way."
    ("not sure, enough to pay the bills", False),
    ("idk, what do you mean?", True),
    ("what do you mean", True),
])
def test_a_shrug_in_front_of_an_answer_is_not_asking_what_we_mean(said, clarify):
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="goal_practical", slots={"outcome": "more money"}))
    text, _ = seller.reply(said)
    assert text.startswith(seller.sense.interruptions["clarify"].reply) == clarify


ROUND_5 = [   # live persona calls (round 5): (step, slots, raised, said, step after, the reply starts with or None)
    ("20", {}, (), "because I'm sick of waiting for things to change", "22", None),   # was "No pressure at all"
    ("22", {}, (), "ok", "22", None),                                    # was "Welcome aboard"
    ("22", {}, (), "debit", "end", None),
    ("14", {}, (), "5 grand? that's a lot mate", "m_funded", None),       # was taken as a nod
    ("m_funded", {}, ("money",), "I don't have 5k lying around", "m_funded", None),   # was "think it over"
    ("m_think_what", {}, ("research",), "mostly whether it actually works for people", "m_reframe1", None),   # was money
    ("03", {}, (), "dunno, a year?", "04", None),                         # was "I'll find out and let you know"
    ("03", {}, (), "honestly I don't trust most of these online things", "03", None),
    ("goal_practical", {"outcome": "a side income"}, (), "ok well, an extra few hundred a month would help with the mortgage", "goal_identity", None),
    ("goal_practical", {"outcome": "out of the rat race"}, (),
     "not dreading Mondays, and having a bit more cash to actually enjoy life rather than just surviving", "goal_identity", None),
    ("01", {}, (), "how'd you get my number", "01", "You filled in an application"),   # was "Good to know."
    ("01", {}, (), "hey sorry, did you catch the match last night?", "01", "Ha, all good here"),
    ("01", {}, (), "fine. more money obviously", "goal_practical", "What are you hoping to achieve with more money?"),
    ("m_funded", {}, ("money",), "can I split it into payments?", "m_funded", "There are ways to make the investment work"),
    ("m_close2", {}, ("fear",), "credit", "22", None),   # was "No rush, even a rough idea helps."; a way to pay goes to paying
    ("19", {}, (), "debit", "22", None),   # one shared list for every "jumping in?" (answers.yaml); was asked again
    ("19", {}, (), "yes let's do it", "20", None),   # a plain yes still sells itself first
    ("03", {}, (), "within a year ideally", "03", None),   # when they want it, not how long: asked again
    ("03", {}, (), "because my job could go any day, there's layoffs", "03", None),
    ("03", {}, (), "i guess 3 years, what about you?", "04", None),   # reply.py: the answer is kept beside the question
    ("06", {}, (), "nothing, why do you ask?", "08", None),
    ("03", {}, (), "two years, and what's the price", "04", "Fair question"),
    ("05", {}, (), "ok so what's the price", "05", "Fair question"),   # was taken as their answer
    ("03", {}, (), "yeah but how much is it", "03", "Fair question"),   # was ignored
    ("04", {}, (), "shut up and just tell me the price", "04", "Fair question"),
    ("14", {}, (), "5 grand? that's a lot mate", "m_funded", None),   # the worry beside "5 grand?" still leads
    ("goal_practical", {"outcome": "freedom"}, (), "being able to quit my job, and how long is the course?",
     "goal_practical", "It's a 6-month process. What would that actually change"),   # live: the goal was lost; level 1, so the ladder digs
    ("01", {}, (), "money. how much is it anyway", "goal_practical", "Fair question"),
    ("05", {}, (), "no time honestly, are you a bot?", "06", "I'm an AI"),
    ("19", {}, (), "yes, how do I pay?", "22", None),   # the question is itself the answer
    ("17", {}, (), "yes, how do I pay?", "22", None),   # the `pays` shortcut from the price on; was "I'll find out"
    ("16", {}, (), "sounds good, send me the link", "22", None),
    ("15", {}, (), "ok", "16", None),   # a nod still moves the pitch on
    ("18", {}, (), "yes, how do I pay?", "22", None),   # was "Are you aware of the programme?" after the whole pitch
    ("14", {}, (), "5k? that's a lot", "m_funded", None),   # the worry leads, not the price again
    ("03", {}, (), "I don't have time for this", "03", "Fair enough"),   # no span of time: can't be the answer
    ("02", {}, (), "I don't have time for this", "02", "Fair enough"),   # no figure: can't be the answer
]


@pytest.mark.parametrize("step, slots, raised, said, after, starts", ROUND_5)
def test_round_5_live_replies(step, slots, raised, said, after, starts):
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step=step, slots=dict(slots), raised=raised))
    text, _ = seller.reply(said)
    assert seller.state.step == after, text
    assert not text.startswith("Sorry to hear that")   # a worry is not a failed attempt
    assert seller.cfg["uncovered_fallback"] not in text
    if starts:
        assert text.startswith(starts), text


ROUND_6 = [   # whole simulated calls (calls.py personas): (step, slots, raised, said, step after, the reply starts with or None)
    ("m_reframe1", {}, ("research",), "not sure", "m_reframe1_now", None),   # was "let me put it another way" x3: not knowing is no "what do you mean?"
    ("18", {}, (), "not sure", "18", "Put simply"),   # the step's own "unclear" answer, not the clarify sense
    ("goal_practical", {"outcome": "more money"}, (), "what do you mean", "goal_practical", "Fair point"),   # still asks
    ("goal_practical", {"outcome": "more money"}, (), "huh?", "goal_practical", None),   # was saved as their goal
    ("goal_practical", {"outcome": "more money"}, (), "dunno, pay my bills?", "goal_identity", None),   # a rise that answers still answers
    ("08", {}, (), "yeah", "09", None),   # its ack answers it (shrug_moves_on); was asked 3 times
    ("08", {}, (), "ok", "09", None),
    ("goal_practical", {"outcome": "more money"}, (),
     "not having to ask my boss for time off, what about you, do you travel much?", "goal_identity", None),   # was heard as "what do you mean?"
    ("03", {}, (), "i guess 3 years, what about you", "04", None),   # "what about you" asks, "?" or not
    ("19", {}, (), "yeah I'm in, how do I pay?", "22", None),   # the question picks the answer; was "Where are you at with it?"
    ("19", {}, (), "ok I'm in, what do I pay with?", "22", None),
    ("m_close2", {}, (), "hmm", "m_close2", "No pressure"),   # thinking, not "what do you mean?" ("huh" is)
    ("m_close1", {}, ("research",), "not yet, how do I pay?", "m_close1", None),   # review: a no takes the question back
    ("m_close1", {}, ("research",), "yeah I'm in, how do I pay?", "22", None),   # review: was taken back (file order)
    ("19", {}, (), "I can't afford it, how do I pay?", "m_funded", None),   # a worry leads; was "Credit or debit?"
    ("19", {}, (), "I can't afford it, what are the payment options?", "m_funded", None),
]


@pytest.mark.parametrize("step, slots, raised, said, after, starts", ROUND_6)
def test_round_6_whole_calls(step, slots, raised, said, after, starts):
    test_round_5_live_replies(step, slots, raised, said, after, starts)


def test_huh_is_never_saved_as_their_goal():
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="goal_practical", slots={"outcome": "more money"}))
    seller.reply("huh?")
    assert "practical" not in seller.state.slots


ROUND_7 = [   # whole simulated calls, round 9: (step, asks, raised, said, step after, the reply starts with or None)
    ("19", 1, (), "ok", "m_identify", None),   # a shrug to "Where are you at with it?" took the yes route: 19 -> 20 -> 22 -> 19
    ("19", 1, (), "yeah", "m_identify", None),
    ("m_funding_options", 0, ("money",), "maybe", "m_funding_options", "No pressure either way."),   # was a yes; and "No rush, even a rough idea helps."
    ("m_funding_options", 0, ("money",), "not sure", "m_funding_options", "No pressure either way."),
    ("m_card", 0, ("money",), "maybe", "m_card", "No pressure either way."),
    ("m_funding_options", 0, ("money",), "I guess so", "22", None),   # a soft yes is still a yes
    ("m_funding_options", 0, ("money",), "probably", "22", None),
    ("m_reframe1_dictate", 0, ("research",), "not sure", "m_reframe2", None),   # was "Why not?"
    ("16", 0, (), "I don't know", "17", None),   # was heard as the scam worry (0.74 to "I don't trust this")
    ("willing", 0, (), "yes definitely", "willing_check", "Just so I'm clear"),   # was "What makes you so different" with no reaction
    ("willing", 0, (), "hell no I'm done settling", "11", None),
    ("willing", 0, (), "yeah I'm willing to change", "11", None),   # a no said as wanting change
    ("willing", 0, (), "no", "11", None),
    ("18", 0, (), "no", "18", "Put simply"),   # a bare "no" was nearest "yes": heard as agrees, on to the close
    ("18", 0, (), "nope", "18", "Put simply"),
    ("18", 0, (), "yes", "19", None),
    ("m_reframe1_dictate", 0, ("think",), "lol", "m_reframe1_dictate", "No pressure either way."),   # was heard as "no"
    ("willing", 0, (), "haha", "willing", "No pressure either way."),
    ("m_identify", 0, (), "just nervous I guess", "m_reframe1", None),   # was "what do you need to think over"
    ("m_identify", 0, (), "time", "m_reframe1", None),
    ("m_identify", 0, (), "I'm too busy with work", "m_reframe1", None),
    ("m_identify", 0, (), "I need to think about it", "m_think_what", None),   # think still thinks
    ("m_identify", 0, (), "I need more time", "m_think_what", None),
    ("05", 0, (), "I don't have time", "06", None),   # a real answer, never the frustration line
    # round 10
    ("05", 0, (), "why do you ask?", "05", "It helps me see"),   # was "I don't know that one offhand, I'll find out"
    ("03", 0, (), "does that matter?", "03", "It helps me see"),
    ("03", 0, (), "3 years, why do you ask?", "04", "It helps me see"),   # the 3 years kept
    ("05", 0, (), "that's important to me", "06", None),   # said, not asked: an answer (0.86 to "why is that important")
    ("05", 0, (), "that matters to me", "06", None),
    ("02", 0, (), "what do most people say?", "02", "There's no right answer"),
    ("09", 0, (), "what most people do is give up", "belief_origin", None),
    ("01", 0, (), "what's included?", "01", "Three parts"),
    ("03", 0, (), "how does the programme work?", "03", "Three parts"),   # was the length
    ("03", 0, (), "how long is the programme?", "03", "It's a 6-month process."),
    ("m_partner_proceed", 0, ("partner",), "I'd have to ask my wife", "m_open_wallet", None),   # was a yes
    ("m_partner_proceed", 0, ("partner",), "it's my decision", "m_partner_close", None),
    ("01", 0, (), "to earn 2500 a month on the side", "goal_practical", None),   # was no goal, asked again
    ("m_scam", 0, ("scam",), "how do I know this isn't a scam?", "m_scam", "No pressure either way."),   # was "I'll find out"
    # round 11
    ("03", 0, (), "3 years, sorry, 2 years", "04", "24 months"),   # was 36: the 3 they took back
    ("03", 0, (), "since I started the business 3 years ago", "04", "36 months"),   # was a failed attempt ("Sorry to hear that")
    ("03", 0, (), "I tried dropshipping and it failed", "03", "Sorry to hear that"),   # still a failed attempt
    ("03", 0, (), "not long", "04", "So what made it come up for you now?"),   # was "so many nights, months and years"
    ("03", 0, (), "a few weeks", "04", "So what made it come up for you now?"),
    ("03", 0, (), "a long time", "04", "If this has been on your mind"),   # a long time is not recent
    ("03", 0, (), "ages", "04", "If this has been on your mind"),
    ("03", 0, (), "why would I tell you that?", "03", "It helps me see"),   # was "I'll find out"
    ("05", 0, (), "sorry, where were we?", "05", "Of course, let me ask that again."),   # was "sorry" taken as the answer
    ("01", 0, (), "a bit of extra income", "goal_practical", None),   # was no goal, asked again
    ("01", 0, (), "sorry, my kid is yelling", "01", "No problem, take your time."),   # "sorry," is no correction here
    ("goal_identity", 0, (), "can you do it for 3k?", "goal_identity", "Let's see if it's even right for you first"),   # was "I'll find out"
    ("14", 0, (), "can you do it for 3k?", "14", "The price is $5k, but"),
    # round 12
    ("03", 0, (), "a while", "04", "If this has been on your mind"),   # was recent: "So what made it come up for you now?"
    ("03", 0, (), "half a year", "04", "6 months"),   # was 12
    ("goal_practical", 0, (), "is it all online?", "goal_practical", "We work with people all around the world"),   # was "I'll find out"
    ("goal_identity", 0, (), "do I get one to one calls?", "goal_identity", "Three parts"),
    ("04", 0, (), "is there a guarantee?", "04", "Fair question."),   # was the scam worry
    ("14", 0, (), "how is this any different from the others?", "14", "It's not just a course"),
    ("01", 0, (), "I want to replace my salary", "goal_practical", "What are you hoping to achieve by being able to replace your salary?"),
    ("01", 0, (), "i want to make money online so i can quit my job and spend more time with my kids", "goal_identity", None),   # was asked again
    ("01", 0, (), "I want to make money online but I don't know how", "01", None),   # still no goal
    ("goal_practical", 0, (), "more money, so I can pay my bills", "goal_identity", None),
    # round 13
    ("04", 0, (), "are you a real person?", "04", "I'm an AI playing the salesperson"),   # was the fallback
    ("goal_identity", 0, (), "what's your name?", "goal_identity", "I'm an AI playing the salesperson"),
    ("04", 0, (), "because money is nice?", "05", None),   # was taken as a question
    ("03", 0, (), "a year, no, two years", "04", "24 months"),   # was 12
    ("03", 0, (), "2y", "04", "24 months"),   # was no number
    ("01", 0, (), "Well it's a long story. I've been a nurse for twelve years and I love it but the shifts are killing me. "
                  "I want something online that pays the bills so I can cut down my hours.", "goal_practical",
     "What are you hoping to achieve by being able to cut down your hours?"),   # was heard as no goal
    ("01", 0, (), "I want more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "It's about them"
    ("01", 0, (), "i want more money for my family", "goal_practical", "So this isn't really about the money"),
    ("01", 0, (), "who is this?", "01", "I'm an AI playing the salesperson"),   # guard: near "who am I talking to", got nothing
    ("01", 0, (), "who are you?", "01", "We help people build their own business"),   # guard: still the intro
    # round 14
    ("01", 0, (), "what about you?", "01", "I'm the AI playing the salesperson"),   # was the fallback
    ("goal_practical", 0, (), "how much do you make?", "goal_practical", "I'm the AI playing the salesperson"),  # was the price
    ("19", 0, (), "would you do it?", "19", "I'm the AI playing the salesperson"),
    ("02", 0, (), "how much do your clients make?", "02", "Honestly, results depend"),   # was the fallback
    ("05", 0, (), "how long does it take to see results?", "05", "Honestly, results depend"),
    ("goal_practical", 0, (), "that's not what I said", "goal_practical", "Sorry, I got that wrong."),  # was kept as the goal
    ("04", 0, (), "you're not listening", "04", "Sorry, I got that wrong."),
    ("01", 0, (), "earn an extra three grand a month", "goal_practical", None),   # was asked again: too close to call
    ("goal_practical", 0, (), "hmm let me think", "goal_practical", None),   # was "What do you mean by hmm let you think?"
    ("19", 0, (), "let me think about it", "m_think_what", "Sure. What specifically"),   # was heard as a shrug
    ("20", 0, (), "I just need a minute", "20", "No problem, take your time."),   # was saved as the reason, then payment
    ("19", 0, (), "I need to think about it", "m_think_what", "Sure. What specifically"),   # guard
    ("19", 0, (), "let me think", "19", None),   # guard: thinking now, not a worry
    ("03", 0, (), "how long is the programme?", "03", "It's a 6-month process"),   # guard: still the length
    ("goal_practical", 0, (), "how much is it?", "goal_practical", "Fair question. I'll give you the exact price"),  # guard
    ("19", 0, (), "no, but how does it work", "19", "Three parts"),   # round 14 replay: was left unanswered
    ("05", 0, (), "does it actually work?", "05", "Honestly, results depend"),   # guard: not how it works
    # round 15
    ("01", 0, (), "is this call recorded?", "01", "Fair question. I'll make sure you have that in writing"),  # was the fallback
    ("goal_practical", 0, (), "will you sell my data?", "goal_practical", "Fair question. I'll make sure"),
    ("02", 0, (), "do you need my bank details?", "02", "Only if you decide to go ahead."),   # was how we got their number
    ("19", 0, (), "do I have to give my card now?", "19", "Only if you decide to go ahead."),   # was the fallback
    ("04", 0, (), "can I start next month?", "04", "We'll sort a start date"),   # was the fallback
    ("19", 0, (), "when does it start?", "19", "We'll sort a start date"),
    ("01", 0, (), "how long is this call?", "01", "Not long, just a few questions"),
    ("goal_practical", 0, (), "what happens next?", "goal_practical", "First we see if this is a fit"),
    ("04", 0, (), "can you email me the details?", "04", "I can send the details after"),   # was how we got their number
    ("04", 0, (), "is it worth it though?", "04", "That's exactly what these questions are for"),
    ("01", 0, (), "what's in it for you?", "01", "I'm the AI playing the salesperson"),
    ("19", 0, (), "why should I trust you?", "m_scam", None),   # was the fallback
    ("19", 0, (), "can I call you back?", "m_think_what", "Sure. What specifically"),   # was the fallback
    ("04", 0, (), "because my kid just started school and money is tight", "05", None),   # was "I haven't mentioned a price yet"
    ("04", 0, (), "is this a scam?", "04", "Fair question, there's a lot of shady stuff"),   # guard: still asks
    ("06", 0, (), "how did you get my number", "06", "You filled in an application"),   # guard: still how we got it
    ("03", 0, (), "how long is the programme?", "03", "It's a 6-month process"),   # guard: not the call length
    ("03", 0, (), "hang on", "03", "No problem, take your time."),   # was torn with leaving, asked again
    ("03", 0, (), "can we pause for a sec", "03", "No problem, take your time."),   # was the fallback
    ("03", 0, (), "be right back", "03", "No problem, take your time."),   # was asked again
    ("19", 0, (), "do I have to pay today?", "19", "Only if you decide to go ahead."),
    ("03", 0, (), "a bit", "04", None),   # guard: how long, never a pause
    ("01", 0, (), "so I can quit my job, but how long does it take?", "goal_practical", "It's a 6-month process."),   # guard: not the call
    ("03", 0, (), "tiktok", "03", "Roughly, is it more like months"),   # was "take your time" (0.67 to a pause)
    ("19", 0, (), "hang on a minute, that's a lot of money", "m_funded", None),   # was torn, saved as a yes
    ("19", 0, (), "hold on, how much?", "19", "It's a 6-month process and the investment"),   # was unclear
    ("19", 0, (), "wait what?", "19", "Fair point, let me put it another way."),   # was the fallback
    ("19", 0, (), "what's the catch?", "m_scam", None),   # was the fallback
    ("19", 0, (), "what if it doesn't work?", "m_reframe1", None),   # was the fallback
    ("04", 0, (), "what if it doesn't work?", "04", "That's fair. That's what this call is for"),   # was the fallback
    ("19", 0, (), "hold on a second", "19", "No problem, take your time."),   # guard: still a pause
    ("22", 0, (), "debit card is ok?", "end", "Perfect."),   # was "Only if you decide to go ahead" (a fact beat paying)
    ("22", 0, (), "can I pay by card?", "end", "Perfect."),   # was "There are ways to make the investment work"
    ("22", 0, (), "what happens to the card?", "22", None),   # guard: a real question, never paid
    ("18", 0, (), "hmm let me think", "18", "Put simply"),   # was "take your time" forever
    ("18", 0, (), "give me a sec", "18", "No problem, take your time."),   # guard: still a pause
    # round 16
    ("01", 0, (), "make money online, but I've been burnt before", "01", "That's fair. That's what this call is for"),   # was the worry only, the goal lost
    ("01", 0, (), "for my kids", "goal_practical", None),   # was a pause (0.79 to "hang on, my kids need me")
    ("01", 0, (), "hang on, the kids need me", "01", "No problem, take your time."),   # guard: still a pause
    ("06", 0, (), "ok?", "06", None),   # was "I'll find out": filler with a rise asks nothing
    ("01", 0, (), "what kind of business is this?", "01", "We help people build their own business online"),   # was the fallback
    ("01", 0, (), "do you have reviews?", "01", "Fair question. I'll show you what others have done"),   # was the fallback
    ("goal_practical", 0, (), "how many people have done it?", "goal_practical", "Fair question. I'll show you"),
    ("goal_practical", 0, (), "can I see some testimonials?", "goal_practical", "Fair question. I'll show you"),
    ("goal_practical", 0, (), "is there a community?", "goal_practical", "Three parts"),   # was the fallback
    ("goal_practical", 0, (), "do you like your job?", "goal_practical", "I'm the AI playing the salesperson"),
    ("goal_practical", 0, (), "what time is it there?", "goal_practical", "Ha, all good here."),   # was when it starts
    ("22", 0, (), "is there a deposit?", "22", "There are ways to make the investment work"),   # was the fallback
    ("22", 0, (), "do you take klarna?", "22", "There are ways to make the investment work"),
    ("22", 0, (), "do you take paypal?", "end", "Perfect."),   # guard: still pays
    ("04", 0, (), "sorry, I'm driving", "later", "No problem. Let's book a follow-up call"),   # was saved as their reason
    ("05", 0, (), "I can't talk right now", "later", None),
    # round 17
    ("03", 0, (), "too long", "04", "If this has been on your mind"),   # was "Fair enough, I'll keep this quick"
    ("03", 0, (), "way too long", "04", "If this has been on your mind"),
    ("03", 0, (), "this is taking too long", "03", "Fair enough, I'll keep this quick."),   # guard: still annoyed
    ("01", 0, (), "nah", "01", "What are you actually hoping to achieve?"),   # was "let me put it another way"
    ("willing", 0, (), "nah", "11", None),   # guard: still a no
    ("02", 0, (), "can I speak to your manager?", "02", "I'm an AI playing the salesperson"),   # was the fallback
    ("02", 0, (), "can I talk to someone else?", "02", "I'm an AI playing the salesperson"),
    # round 18
    ("22", 0, (), "can I pay next week?", "22", "There are ways to make the investment work"),   # was the fallback
    ("19", 0, (), "can I pay later?", "19", "There are ways to make the investment work"),
    ("22", 0, (), "can I pay on friday?", "22", "There are ways to make the investment work"),
    ("01", 0, (), "are you reading from a script?", "01", "I'm an AI playing the salesperson"),   # was the fallback
    ("goal_practical", 0, (), "is this a sales call?", "goal_practical", "I'm an AI playing the salesperson"),
    ("01", 0, (), "I'd rather not say", "01", "That's fine, no pressure."),   # was "Sorry, I got that wrong."
    ("04", 0, (), "none of your business", "04", "That's fine, no pressure."),   # was saved as their reason
    ("02", 0, (), "that's private", "02", "That's fine, no pressure."),
    ("04", 0, (), "I don't want to keep living like this", "05", None),   # guard: a real answer
    ("01", 0, (), "I'd rather be my own boss", "goal_practical", None),   # guard
    ("01", 0, (), "I'm not really interested to be honest", "01", "What are you actually hoping to achieve?"),   # not "private": "That's fine, no pressure."
    ("02", 0, (), "I'd rather keep that to myself", "02", "That's fine, no pressure."),   # was 0.73
    ("02", 0, (), "I'm not telling you", "02", "That's fine, no pressure."),   # was "Sorry, I got that wrong."
]


@pytest.mark.parametrize("step, asks, raised, said, after, starts", ROUND_7)
def test_round_7_whole_calls(step, asks, raised, said, after, starts):
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step=step, asks=asks, raised=raised))
    text, _ = seller.reply(said)
    assert seller.state.step == after, text
    if starts:
        assert text.startswith(starts), text


def test_an_answer_fixed_a_turn_later_is_kept():
    """Round 17: "sorry I meant 3k not 2k" to "how long?" was saved as how long they had been thinking."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="02"))
    seller.reply("2k")
    text, _ = seller.reply("sorry I meant 3k not 2k")
    assert seller.state.slots == {"number": "3k"} and seller.state.step == "03", (text, seller.state.slots)
    text, _ = seller.reply("a year")
    assert seller.state.slots == {"number": "3k", "years": "a year"} and seller.state.step == "04", text


def test_a_real_word_is_kept_as_they_said_it():
    """Whole calls: "just not drown in debt" was saved as "just not down in debt" (a typo of "down")."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="goal_practical"))
    seller.reply("just not drown in debt")
    assert seller.state.slots["practical"] == "just not drown in debt"


def test_what_they_take_back_and_say_early_is_kept_right():
    """Whole calls: "3k, no wait, more like 4k" kept the 3k; the time said in the first reply was asked again."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="02"))
    seller.reply("3k, no wait, more like 4k")
    assert seller.state.slots["number"] == "more like 4k" and seller.state.step == "03"
    seller.reset(ScriptState(step="01"))
    seller.reply("I want to quit my job, I need about 4k a month and I've been thinking about it for 2 years")
    assert seller.state.slots["years"] == "2 years" and seller.state.slots["number"] == "4k a month"


def test_a_worry_asked_again_before_the_price_is_still_the_worry():
    """Whole calls: "how do I know this isn't a scam?" asked a 2nd time got "I'll find out"; said as a statement
    once parked it answers the step."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="04"))
    first, _ = seller.reply("how do I know this isn't a scam?")
    again, _ = seller.reply("how do I know this isn't a scam?")
    assert seller.state.step == "04" and seller.state.parked, (first, again)
    assert again.startswith(seller.sense.park_again) and first != again, again
    seller.reply("I'm not sure I trust it")
    assert seller.state.step == "05"
