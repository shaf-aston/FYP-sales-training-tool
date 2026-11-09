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
from core.buy_mode.script_engine.hear.reply import Reader
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
    only_asked = {k for k, i in load_common_sense().interruptions.items() if i.only_asked}  # heard only in a question
    reader = Reader(cfg, [], lambda _: False)
    data = yaml.safe_load((ROOT / "tests/data/script_replies.yaml").read_text(encoding="utf-8"))
    embedder.warm([e for labels in _contexts().values() for ex in labels.values() for e in ex])
    rows, times = [], []
    for context, labels in _contexts().items():
        for expected, replies in data[context].items():
            for reply in replies:
                start = time.perf_counter()
                heard = labels if context != "common_sense" or reader.read(reply).asked else {
                    k: v for k, v in labels.items() if k not in only_asked}
                match = listener.match(reply, heard)
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
    ("m_close2", {}, ("fear",), "credit", "end", None),   # was "No rush, even a rough idea helps."; a way to pay named ends the call (round 27)
    ("19", {}, (), "debit", "end", None),   # one shared list for every "jumping in?" (answers.yaml); was asked again; named, so the end (round 27)
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
    ("16", {}, (), "sounds good, send me the link", "end", None),   # a way to pay named ends the call (round 27)
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
    ("19", 1, (), "ok", "20", None),   # the second ask is a yes/no ("Is this something you can see yourself doing?"): "ok" is a yes
    ("19", 1, (), "yeah", "20", None),   # (all "ok" still ends: 19 -> 20 -> 22 -> 19 twice, then a follow-up call)
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
    ("05", 0, (), "sorry, where were we?", "05", "Of course, let me say that again."),   # was "sorry" taken as the answer
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
    ("01", 0, (), "I'm not really interested to be honest", "later", "No problem."),   # not "private": "That's fine, no pressure."; round 53 cuts "to be honest", so it is a polite no like "honestly not interested"
    ("01", 0, (), "not really interested tbh", "later", "No problem."),   # round 53: same no with "tbh"
    ("02", 0, (), "I'd rather keep that to myself", "02", "That's fine, no pressure."),   # was 0.73
    ("02", 0, (), "I'm not telling you", "02", "That's fine, no pressure."),   # was "Sorry, I got that wrong."
    # round 19
    ("22", 0, (), "how do I pay?", "22", "Which works better for you, credit or debit?"),   # was the fallback
    ("19", 0, (), "how do I pay?", "22", "How would you like to process the investment?"),   # guard: still pays
    ("19", 0, (), "can I cancel anytime?", "19", "Fair question. I'll confirm exactly how that works"),   # was the fallback
    ("19", 0, (), "is there a contract?", "19", "Fair question. I'll confirm exactly how that works"),   # was heard as unsure
    ("19", 0, (), "can I do it alongside my job?", "19", "Fair question. We'll plan it around the time"),   # was the fallback
    ("01", 0, (), "how many hours a week does it take?", "01", "Fair question. We'll plan it around the time"),   # was "It's a 6-month process."
    ("01", 0, (), "how long does it take?", "01", "It's a 6-month process."),   # guard
    ("goal_practical", 0, (), "more time", "goal_identity", None),   # was "Fair enough, I'll keep this quick."
    ("goal_practical", 0, (), "this is taking too long", "goal_practical", "Fair enough, I'll keep this quick."),   # guard
    ("01", 0, (), "what do I want to achieve?", "01", "Fair point, let me put it another way."),   # was the AI line
    ("02", 0, (), "how much do I need?", "02", "Fair point, let me put it another way."),   # was the price line
    ("20", 0, ("fear",), "I'm scared", "20", "That's normal, it's a big step. What makes you want to go for it anyway?"),   # was payment
    ("20", 0, (), "I'm nervous", "20", "That's normal, it's a big step."),   # was the whole fear talk again after a yes
    ("20", 0, ("fear",), "because I'm sick of my job", "22", None),   # guard: their reason
    ("20", 0, ("fear",), "idk I just feel ready", "22", None),   # guard: replay, was heard as the fear
    # round 20
    ("20", 0, ("partner",), "I need to ask my husband first", "m_partner_here", "Okay. So, if your partner"),   # was their reason, then payment
    ("20", 0, (), "he decides the money stuff", "m_partner_here", None),   # was their reason, then payment
    ("m_reframe1", 0, ("fear",), "I'm scared", "m_reframe1_now", None),   # guard: in its own talk a worry answers
    ("04", 0, (), "my husband earns most of the money", "05", None),   # guard: an answer, not the partner
    ("01", 0, (), "is this one of those get rich quick things?", "01", "Fair question, there's a lot of shady stuff online."),   # was "I'll find out"
    ("01", 0, (), "is this MLM?", "01", "Fair question, there's a lot of shady stuff online."),   # was "I'll find out"
    ("19", 1, (), "yes", "20", "What makes you say that?"),   # was heard as saying nothing to "Where are you at with it?"
    ("goal_identity", 0, (), "what would it change?", "goal_identity", "Fair point, let me put it another way."),   # was "I'll find out"
    ("01", 0, (), "I'm a student and need cash", "goal_practical", None),   # round 20: was heard as no goal
    ("01", 0, (), "I need money", "goal_practical", None),   # was heard as the money worry before any price
    ("01", 0, (), "how long would I be in it for?", "01", "It's a 6-month process."),   # was the hours-a-week line
    ("01", 0, (), "mroe money", "goal_practical", "What are you hoping to achieve with more money?"),   # was said back with the typo
    ("03", 0, (), "how long what?", "03", "Fair point, let me put it another way."),   # moved on unanswered
    ("04", 0, (), "my loan isn't enough", "05", None),   # was "I haven't mentioned a price yet"
    ("04", 0, (), "is this a scam?", "04", "Fair question"),   # guard: a worry asked is still the worry
    ("m_open_wallet", 0, (), "can we do option 2?", "22", None),   # was "Sure, let me ask that again" (the talk is not the question)
    # round 21
    ("03", 0, (), "what?", "03", "Fair point, let me put it another way."),   # was "I'll find out"
    ("goal_identity", 0, (), "sorry what?", "goal_identity", "Fair point, let me put it another way."),
    ("19", 0, (), "y", "20", None),   # was not a yes
    ("05", 0, (), "y", "05", "No rush"),   # "y" to an open question says nothing: never saved as their reason
    ("19", 0, (), "can I get it cheaper?", "19", "The price is"),   # was "I'll find out"
    # round 22
    ("20", 0, (), "I'm just not interested", "19", "No pressure at all."),   # was payment
    ("19", 0, (), "I don't see why not", "20", None),   # was not yet
    ("19", 0, (), "I don't see myself doing this", "19", None),   # guard: still not yet
    ("01", 0, (), "well it started when my dad got ill last year and I had to take time off work and since then money has been tight and I just want to get back on my feet", "goal_practical", None),   # was "I haven't mentioned a price yet"
    ("01", 0, (), "I can't afford that", "01", "I haven't mentioned a price yet"),   # guard: paying us is still the worry
    ("01", 0, (), "1. more money 2. more time", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with 1?"
    # round 23
    ("02", 0, (), "a month?", "02", "Fair point, let me put it another way."),   # was "I'll find out"
    ("01", 0, (), "achieve?", "01", "Fair point, let me put it another way."),   # was the AI line
    ("22", 0, (), "debit?", "end", None),   # guard: picks one of the choices
    ("01", 0, (), "lol idk, money?", "goal_practical", None),   # guard: the answer said with a rise
    ("20", 0, (), "not for me", "19", "No pressure at all."),   # was payment
    ("20", 0, (), "no thanks", "19", "No pressure at all."),   # guard: passes on both
    ("19", 0, (), "yes but what if I can't keep up?", "m_reframe1", None),   # was "What makes you say that?"
    ("01", 0, (), "depends what you're offering", "01", "We help people"),   # was "What do you mean by depends..."
    ("01", 0, (), "it depends on what it is", "01", "We help people"),
    # round 24
    ("01", 0, (), "I was wondering how this works first", "01", "Three parts"),   # was "What are you actually hoping to achieve?"
    ("01", 0, (), "I was wondering if you could tell me more", "01", "We help people"),
    ("goal_practical", 0, (), "I'd like to know the price first", "goal_practical", "Fair question."),
    ("04", 0, (), "I want to know more", "04", "We help people"),
    ("01", 0, (), "I want to know the price", "01", "Fair question."),   # guard: still the price
    ("02", 0, (), "about 2k, I was wondering what it costs", "03", "Fair question."),   # the answer kept, the question answered
    ("19", 0, (), "yes, sorry", "20", None),   # was unsure
    ("19", 0, (), "would it be ok to say yes?", "20", None),   # was unsure
    ("01", 0, (), "is it ok to say quit my job?", "goal_practical", "What are you hoping to achieve by being able to quit your job?"),
    ("01", 0, (), "sorry for the long message but I want to quit my job", "goal_practical", None),
    ("03", 0, (), "3k a month", "03", "Roughly, is it more like months, or a few years?"),   # was saved as "1 months"
    ("03", 0, (), "a month", "04", "1 month... Damn."),   # was "1 months... Damn."
    ("01", 0, (), "kind of more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with kind of more money?"
    ("01", 0, (), "50% more income", "goal_practical", "What are you hoping to achieve with 50% more income?"),   # was "50 more income"
    # round 25
    ("02", 0, (), "2k, is that a lot?", "03", "There's no right answer here"),   # was "I haven't mentioned a price yet"; round 44: the question is answered first
    ("14", 0, (), "is that a lot?", "m_funded", None),   # guard: after the price it is the money worry
    ("03", 0, (), "A year. Is that normal?", "04", "There's no right answer here"),   # was no answer to the question
    ("01", 0, (), "what do most people say?", "01", "There's no right answer here"),   # guard: asked alone, the step is asked again
    ("01", 0, (), "more money, actually no, more time", "goal_practical", "What are you hoping to achieve with more time?"),   # was "...with more money actually no more time?"; now the same as a bare "more time"
    ("22", 0, (), "credit, is that ok?", "end", "Perfect."),   # round 25 replay: got "There's no right answer here"
    ("03", 0, (), "2 years, is that ok?", "04", "24 months"),
    # round 26
    ("01", 0, (), "oh great, another sales call. more money I guess", "goal_practical", "I'm an AI playing"),   # was the honest line, "more money" lost
    ("03", 0, (), "how long? hmm, about 2 years", "04", "24 months"),   # was "So what made it come up for you now?"
    ("goal_practical", 0, (), "achieve? quit my job", "goal_practical", "What would that actually change"),   # was "What do you mean by achieve?"
    ("04", 0, (), "I guess my car loan?", "05", None),   # was "I'll find out"
    ("22", 0, (), "debit because I don't do credit", "end", "Perfect."),   # was asked again
    ("19", 0, (), "I wouldn't say no", "20", None),   # was "That's fine, no pressure."
    ("01", 0, (), "come again?", "01", "Of course, let me say that again"),   # was "I'll find out"
    ("01", 0, (), "say what now?", "01", "Of course, let me say that again"),   # was saved as their answer
    ("22", 0, (), "which?", "22", "Fair point"),   # was "I'll find out"
    ("22", 0, (), "sorry, which one?", "22", "Fair point"),
    ("03", 0, (), "a fortnight", "04", "So what made it come up"),   # was asked again
    ("03", 0, (), "how long?", "03", "Fair point"),   # guard: said back alone, it is put another way
    ("02", 0, (), "about 2k, how much is it?", "03", "Fair question"),   # guard: their own question is answered
    ("01", 0, (), "is this a sales call", "01", "I'm an AI playing"),   # guard: asked alone, the step is asked again
    ("03", 0, (), "thanks for asking, about 2 years", "04", "You're welcome. 24 months"),   # was "You're welcome." and the 2 years lost
    ("02", 0, (), "sorry, how much what?", "02", "Fair point"),   # was the price: "sorry" counted against the question said back
    # round 27
    ("19", 0, (), "yes, debit", "end", "Perfect."),   # was "jumping in?" asked again, then the payment asked
    ("19", 0, (), "debit", "end", "Perfect."),
    ("m_close1", 0, (), "debit", "end", "Perfect."),
    ("15", 0, (), "debit", "end", "Perfect."),
    ("19", 0, (), "yes, how do I pay?", "22", "How would you like"),   # guard: no way named, the payment is asked
    ("01", 0, (), "more money, about 2k a month", "goal_practical", "What are you hoping to achieve with more money?"),   # was "about 2k a month" said back
    ("01", 0, (), "well, to be honest with you, more money", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "um so basically i want more money because like rent", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "more money, well, more time really", "goal_identity", "And what would"),   # was "more money" kept
    ("goal_practical", 0, (), "pay rent", "goal_identity", None),   # was heard as level 1 and asked again
    # round 28
    ("01", 0, (), "can we skip to the price", "01", "Fair question."),   # was "What do you mean by skip?"
    ("goal_identity", 0, (), "skip", "goal_identity", "That's fine, no pressure."),   # was heard as their answer
    ("04", 0, (), "my job?", "05", None),   # was "I'll find out"
    ("01", 0, (), "my family needs more money", "goal_practical", "So this isn't really about the money.¶It's about ==them==.¶What are you hoping to achieve with more money?"),   # was "my family needs more money" said back
    ("01", 0, (), "more £££", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more?"
    ("01", 0, (), "more money,more time", "goal_practical", "What are you hoping to achieve with more money, more time?"),
    ("19", 0, (), "no yeah", "20", None),   # was heard as unsure
    ("20", 0, (), "no yeah, it makes sense", "22", None),   # was heard as backing out
    ("19", 0, (), "yeah no", "19", None),   # guard: "yeah no" is a no
    ("19", 0, (), "I'll pass", "19", None),   # guard: still not heard as private
    ("02", 0, (), "is there a discount", "02", None),   # guard: still the discount worry
    # round 29
    ("goal_practical", 0, (), "what do you think?", "goal_practical", "There's no right answer here"),   # was "I'll find out"
    ("19", 0, (), "what would you do?", "19", "There's no right answer here"),
    ("02", 0, (), "what's normal?", "02", "There's no right answer here"),
    ("19", 0, (), "would you do it?", "19", "I'm the AI playing the salesperson"),   # guard: still about the seller
    ("22", 0, (), "deb", "end", "Perfect."),   # was "No problem, take your time."
    ("22", 0, (), "one sec, getting my card", "22", "No problem, take your time."),   # was "credit or debit?" again
    ("01", 0, (), "in 5 years I'd like to be rich", "goal_practical", "What are you hoping to achieve by being rich?"),   # was the plain line
    ("01", 0, (), "my husband wants me to earn more", "goal_practical", "What are you hoping to achieve by being able to earn more?"),
    ("01", 0, (), "more f***ing money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more f ing money?"
    # round 30
    ("01", 0, (), "next", "01", "Sure. What are you actually hoping to achieve?"),   # was "with next?"
    ("goal_practical", 0, (), "continue", "goal_practical", "Sure."),   # was unclear
    ("01", 0, (), "carry on", "01", "Sure."),
    ("goal_practical", 0, (), "quit", "goal_practical", None),   # was heard as leaving the call
    ("goal_practical", 0, (), "bye", "later", None),   # guard: still leaving
    ("01", 0, (), "**more money**", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more?"
    ("03", 0, (), "~a year~ two years", "04", "24 months"),   # was "12 months"
    ("01", 0, (), "same as everyone, more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was said back whole
    # round 31
    ("01", 0, (), "what am I hoping to achieve? more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "I'm the AI"
    ("01", 0, (), "more money, thank you", "goal_practical", "What are you hoping to achieve with more money?"),   # thanks said back
    ("01", 0, (), "💰💰💰", "goal_practical", None),   # was "with?" or nothing
    ("01", 0, (), "I want to by a house", "goal_identity", None),   # was "What do you mean by wanting to buy a house?"
    ("01", 0, (), "I want to buy a house", "goal_identity", None),
    ("goal_practical", 0, (), "🏠 for my family", "goal_identity", None),   # was unclear
    ("goal_practical", 0, (), "next", "goal_practical", "Sure."),   # guard: alone it still nudges
    ("01", 0, (), "I want to achieve financial freedom", "goal_practical", "What are you hoping to achieve with financial freedom?"),   # was "by being able to achieve"
    # round 32
    ("01", 0, (), "moreee moneyyy", "goal_practical", "What are you hoping to achieve with more money?"),   # was the plain line
    ("03", 0, (), "a yearrr", "04", "12 months"),   # was asked 3 times
    ("02", 0, (), "Around two thousand a month, if that helps.", "03", "How long"),   # was "You're welcome."
    ("02", 0, (), "thanks", "02", "You're welcome."),   # guard: thanks alone is still thanks
    ("01", 0, (), "Could I possibly say more money, please?", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with could you possibly say more money?"
    ("01", 0, (), "loads more dosh", "goal_practical", "What are you hoping to achieve with loads more money?"),   # was the plain line
    # round 33
    ("02", 0, (), "sorry was driving, 2k", "03", "How long"),   # was heard as leaving: the call ended
    ("02", 0, (), "sorry kids were shouting, 2k", "03", "How long"),   # was "No problem, take your time."
    ("02", 0, (), "sorry, my kid is yelling", "02", "No problem, take your time."),   # guard: a pause now still waits
    ("02", 0, (), "sorry, I'm driving", "later", None),   # guard: still leaving
    ("03", 0, (), "a year, well two", "04", "24 months"),   # was "12 months"
    ("01", 0, (), "what I said", "02", "How much would you need to be making each month to make that happen?"),   # was said back: "to have what you said"
    # round 34
    ("03", 0, (), "6 months, actually more like a year", "04", "12 months"),   # was "6 months"
    ("01", 0, (), "more time, sorry more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more time, sorry more money"
    ("22", 0, (), "which is better?", "22", "There's no right answer"),   # was heard as paying: "Welcome aboard"
    ("22", 0, (), "which is easier?", "22", "There's no right answer"),   # the same
    ("22", 0, (), "which do you recommend?", "22", "There's no right answer"),   # was "I'll find out"
    ("22", 0, (), "can I use paypal?", "end", "Perfect."),   # guard: a question naming a way to pay still pays
    ("22", 0, (), "whichever is easier", "end", "Perfect."),   # guard: leaving the choice to us still pays
    ("01", 0, (), "sorry I was in a meeting, more money", "goal_practical", "What are you hoping to achieve with more money?"),   # the aside was kept: "What are you hoping that would get you?"
    ("01", 0, (), "more money, sorry had a call", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "I was broke, more money", "goal_practical", "What are you hoping that would get you?"),   # guard: no break, kept whole
    ("01", 0, (), "for my wife", "goal_practical", "What are you hoping to achieve with your wife?"),   # guard: round 33's "what I said" as a goal example took it (0.67)
    # round 35
    ("05", 0, (), "no thank you", "later", "No problem. Let's book a follow-up call"),   # was kept as the answer, 25 steps on
    ("goal_practical", 0, (), "no thanks", "later", "No problem."),   # was unclear, then moved on
    ("05", 0, (), "honestly not interested", "later", "No problem."),
    ("17", 0, (), "no thanks", "18", None),   # `yes_no`: a plain no, never leaving
    ("05", 0, (), "I'm not interested in money", "06", None),   # guard: an answer (0.86 to "I'm not interested")
    ("willing", 0, (), "no thank you", "11", None),   # guard: a plain no to a yes-or-no question
    ("20", 0, (), "no thank you", "19", None),   # guard: the close hears it its own way (backs out)
    ("m_close1", 0, (), "I'm not interested", "m_reframe2", None),   # guard: the soft close goes on
    ("05", 0, (), "because", "05", "No rush"),   # was saved as the answer at every open step
    ("20", 0, (), "because", "20", None),   # was unclear, then payment
    ("05", 0, (), "because I hate my job", "06", None),   # guard: a reason
    ("19", 0, (), "should I?", "19", "There's no right answer"),   # was "I'll find out"
    ("19", 0, (), "should I do it?", "19", "There's no right answer"),   # was "I'm the AI playing the salesperson"
    # round 36
    ("19", 0, (), "my partner said yes", "20", None),   # was the partner objection: "if your partner was here..."
    ("19", 0, (), "my partner is fine with it", "20", None),
    ("19", 0, (), "my wife said no", "m_partner_here", None),   # guard: a no from them is still about them
    ("19", 0, (), "I need to ask my partner", "m_partner_here", None),   # guard
    ("19", 0, (), "bet", "20", None),   # was unclear, then "safe" ran the soft closes to a follow-up call
    ("05", 0, (), "safe", "05", "No rush"),   # was kept as the answer at every open step
    ("05", 0, (), "I want to feel safe", "06", None),   # guard: a reason
    ("01", 0, (), "money 💰", "goal_practical", "What are you hoping that would get you?"),   # was "with money money?"
    # round 37
    ("04", 0, (), "I told you, my job", "05", None),   # was "Fair point, let me put it another way.", the job lost
    ("03", 0, (), "I already told you, a year", "04", "12 months... Damn."),
    ("04", 0, (), "I told you already", "04", "Fair point"),   # guard: alone it is still "you asked me that"
    ("01", 0, (), "idk more money idk", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more money idk?"
    ("01", 0, (), "more money obviously, stupid question", "goal_practical", "What are you hoping to achieve with more money?"),   # was said back whole
    # round 38
    ("01", 0, (), "hmm let me think", "01", "What are you actually hoping to achieve?"),   # was "let me say that again": thinking out loud is not knowing yet
    ("01", 0, (), "sorry, can you say that again", "01", "Of course, let me say that again."),   # guard
    ("04", 0, (), "next question", "04", "That's fine, no pressure."),   # was saved as the answer
    ("04", 0, (), "pass", "04", "That's fine, no pressure."),
    ("19", 0, (), "I guess so", "20", None),   # a soft yes went into the not-yet talk
    ("19", 0, (), "I suppose so", "20", None),
    ("19", 0, (), "maybe", "19", None),   # guard: still not a yes
    ("19", 0, (), "I guess not", "19", None),   # guard: still not yet
    ("05", 0, (), "Understood.", "05", None),   # was saved as the reason
    ("01", 0, (), "mor mony", "goal_practical", "What are you hoping to achieve with more money?"),   # was unclear
    ("01", 0, (), "u know, more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with u know, more money?"
    # round 39
    ("19", 0, (), "yes sorry", "20", None),   # was unclear ("yes, sorry" was a yes)
    ("19", 0, (), "no sorry", "19", None),   # guard: still not a yes
    ("03", 0, (), "1-2 years", "04", "24 months... Damn."),   # was no number
    ("01", 0, (), "back, more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with back, more money?"
    ("01", 0, (), "I want more money for my family yes", "goal_practical", "So this isn't really about the money."),
    ("01", 0, (), "more money, is that silly?", "goal_practical", "There's no right answer here"),   # was no answer to it
    ("goal_practical", 0, (), "quit my job, is that weird?", "goal_practical", "There's no right answer here"),
    ("04", 0, (), "my job, does that make sense?", "05", "There's no right answer here"),
    # round 40
    ("01", 0, (), "money/time", "goal_practical", "What are you hoping to achieve with money or time?"),   # was "What do you mean by money time?"
    ("01", 0, (), "money and time", "goal_practical", "What are you hoping to achieve with money and time?"),   # was "What do you mean by"
    ("01", 0, (), "time", "goal_practical", None),   # was small talk: "Let's keep the time about you though"
    ("01", 0, (), "um so basically i want more money you know", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "Honestly. More money. That's it.", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "wdym", "01", "Fair point"),   # was unclear
    ("goal_identity", 0, (), "like who?", "goal_identity", "Fair point"),   # was kept as the answer
    ("02", 0, (), "per month?", "02", "Fair point"),   # was the payment plan line
    ("14", 0, (), "a month?", "14", "There are ways to make the investment work"),   # the price line asks nothing: how it is paid
    ("04", 0, (), "what do you mean stopping me?", "04", "Fair point"),   # was "I'll find out"
    ("04", 0, (), "not having enough time", "05", None),   # was "Fair enough, I'll keep this quick"
    ("04", 0, (), "this is taking forever", "04", "Fair enough, I'll keep this quick."),   # guard: still heard
    ("03", 0, (), "1,5 years", "04", "18 months... Damn."),   # was no number
    # round 41
    ("03", 0, (), "if I really think about it, about a year", "04", "12 months... Damn."),   # was "I need to think about it"
    ("03", 0, (), "a yearish", "04", "12 months... Damn."),   # was missed
    ("03", 0, (), "about a year-ish", "04", "12 months... Damn."),   # was no number
    ("03", 0, (), "I need to think about it", "03", "That's fair"),   # guard: still the worry
    ("01", 0, (), "to be completely honest, more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "by being completely honest, more money?"
    ("01", 0, (), "well, to be completely honest with you, I'd say more money", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "more money-ish", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more money-ish?"
    ("01", 0, (), "I suppose more money would be nice", "goal_practical", "What are you hoping to achieve with more money?"),   # was no goal said back
    ("01", 0, (), "finish my degree", "goal_practical", "What are you hoping to achieve by being able to finish your degree?"),   # was "with finish your degree?"
    ("01", 0, (), "open a shop", "goal_practical", None),   # was unclear
    ("05", 0, (), "ok I understand", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "aye", "05", "No rush"),
    ("05", 0, (), "I see", "05", "No rush"),
    ("19", 0, (), "aye", "20", None),   # guard: still a yes
    # round 42
    ("01", 0, (), "im after more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with im after more money?"
    ("03", 0, (), "since last year", "04", "12 months... Damn."),   # was no number
    ("19", 0, (), "go on", "20", None),   # was "Sure. Is this something...?" again
    ("19", 0, (), "fire away", "20", None),   # was unclear
    ("11", 0, (), "go on then", "12", "Sure."),   # was saved as the answer
    ("01", 0, (), "what I'm hoping to achieve is more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was no goal said back
    ("19", 0, (), "what's next?", "19", "Sure."),   # guard: still a nudge
    ("01", 0, (), "because I'm broke, more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was no goal said back
    ("03", 0, (), "since last month", "04", "1 month... Damn."),   # was no number
    ("willing", 0, (), "go on then", "11", "Sure."),
    # round 43
    ("01", 0, (), "I used to run a business, I want that again", "goal_practical", None),   # was "let me say that again"
    ("01", 0, (), "come again?", "01", "Of course, let me say that again."),   # guard: still asks
    ("03", 0, (), "6 weeks", "04", "So what made it come up for you now?"),   # was "so many nights, months and years"
    ("03", 0, (), "10 days", "04", "So what made it come up for you now?"),
    ("03", 0, (), "6 months", "04", "6 months... Damn."),   # guard: still a number
    ("01", 0, (), "something called freedom", "goal_practical", "What are you hoping to achieve with freedom?"),   # was taken as its answer; never a yes to settling
    # round 44
    ("01", 0, (), "money I guess", "goal_practical", "What are you hoping that would get you?"),   # was "What do you mean by money?"
    ("01", 0, (), "no idea, money I guess", "goal_practical", "What are you hoping that would get you?"),
    ("05", 0, (), "alright then", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "okk", "05", "No rush"),
    ("19", 0, (), "depends on the price", "19", "It's a 6-month process and the investment is $5k."),   # was "let me put it another way"
    ("02", 0, (), "2k, is that a lot?", "03", "There's no right answer here"),   # the question got no answer
    ("18", 0, (), "how long is it?", "18", "It's a 6-month process."),   # was "There's no right answer here"
    ("22", 0, (), "💳", "end", None),   # said nothing
    ("willing", 0, (), "yeah I suppose", "willing_check", None),   # guard: still a soft yes
    ("14", 0, (), "is that a lot?", "m_funded", None),   # guard: after the price it is the money worry
    ("03", 0, (), "how long do most people say?", "03", None),   # guard: still no wrong answer
    # round 45
    ("goal_practical", 0, (), "what would I do? quit", "goal_practical", "What would that actually change"),   # was "quit" the call
    ("01", 0, (), "what do you mean? money I suppose", "goal_practical", "What are you hoping that would get you?"),   # the answer was lost
    ("01", 0, (), "what do you mean? I don't know", "01", "Fair point"),   # guard: no answer, still put another way
    ("01", 0, (), "more money like", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with more money like?"
    ("01", 0, (), "money money", "goal_practical", "What are you hoping that would get you?"),   # was "with money money?"
    ("01", 0, (), "honestly i just want more money so i can stop stressing", "goal_practical", "What are you hoping to achieve with more money?"),   # no goal said back
    ("03", 0, (), "a few months maybe", "04", "So what made it come up for you now?"),   # was "so many nights, months and years"
    ("03", 0, (), "a few years", "04", "If this has been on your mind"),   # guard: never recent
    # round 46
    ("22", 0, (), "we're fine", "22", "Which works better for you"),   # was "Welcome aboard" ("we're" spelled "were")
    ("22", 0, (), "either is fine", "end", None),   # guard: a choice still pays
    ("19", 0, (), "I'm in", "20", "What makes you say that?"),   # was asked again: only stop words, so a shrug
    ("18", 0, (), "we're in", "19", None),
    ("m_partner_close", 0, (), "I'm with you", "20", None),
    ("04", 0, (), "money, no, time", "05", None),   # was "Ha, all good here"
    ("04", 0, (), "time", "05", None),
    ("04", 0, (), "how's your day going", "04", "Ha, all good here"),   # guard: still small talk
    ("01", 0, (), "you watching the football later?", "01", "Ha, all good here"),   # guard
    # round 47
    ("goal_practical", 0, (), "yeah. quit.", "goal_practical", "What would that actually change"),   # was "quit" the call
    ("goal_practical", 0, (), "quit lol", "goal_practical", "What would that actually change"),
    ("05", 0, (), "oh sure", "05", None),   # was saved as the reason
    ("05", 0, (), "please go on", "06", "Sure."),
    ("05", 0, (), "oh my boss", "06", None),   # guard
    ("19", 0, (), "ok go on", "20", "What makes you say that?"),   # was asked again
    ("goal_practical", 0, (), "quit, obviously, like everyone", "goal_practical", "What would that actually change"),   # was heard as who they want to be
    ("goal_practical", 0, (), "I don't want to be like everyone else", "02", None),   # guard
    ("18", 0, (), '"ok"', "19", "Do you see yourself jumping in?"),   # was "let me put it another way"; since round 51 a bare "ok" here is a yes
    ("18", 0, (), "yeah, ok", "19", None),   # was "Put simply": the "yeah" was left out
    ("willing", 0, (), "yeah. ok.", "willing_check", None),   # was unclear, so the check was skipped
    # round 48
    ("01", 0, (), "maybe money?", "goal_practical", None),   # was "What do you mean by money?"
    ("goal_practical", 0, (), "maybe quit?", "goal_practical", "What would that actually change"),   # was skipped to who they want to be
    ("01", 0, (), "money?", "01", "Fair point"),   # guard: a bare word asked back is still a question
    ("05", 0, (), "okey-dokey", "05", None),   # was saved as the reason
    ("03", 0, (), "18ish months", "04", "18 months... Damn."),   # the number was lost
    ("03", 0, (), "eighteen-ish months", "04", "18 months... Damn."),
    # round 49
    ("05", 0, (), "k tx", "05", "You're welcome"),   # was saved as the reason
    ("05", 0, (), "of course", "05", None),   # was saved as the reason
    ("05", 0, (), "I'd say ok", "05", None),
    ("05", 0, (), "exactly", "05", None),
    ("05", 0, (), "I'd say my boss", "06", None),   # guard: the lead goes, the answer stays
    ("01", 0, (), "precisely more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "with precisely more money?"
    ("01", 0, (), "money (lots)", "goal_practical", "What are you hoping that would get you?"),   # was "with money lots?"
    ("01", 0, (), "ugh money", "goal_practical", "What are you hoping that would get you?"),   # was "with ugh money?"
    ("19", 0, (), "of course", "20", "What makes you say that?"),   # guard: still a yes
    ("goal_practical", 0, (), "is it ok to say quit?", "goal_practical", "What would that actually change for you, day to day?"),   # ended the call
    ("goal_practical", 0, (), "I'd say quit", "goal_practical", "What would that actually change for you, day to day?"),
    ("goal_practical", 0, (), "quit 100%", "goal_practical", "What would that actually change for you, day to day?"),   # was "What do you mean"
    ("01", 0, (), "more money, if possible", "goal_practical", "What are you hoping to achieve with more money?"),   # was said back whole
    ("01", 0, (), "mo money", "goal_practical", "What are you hoping to achieve with more money?"),
    ("01", 0, (), "I hope to be rich", "goal_practical", "What are you hoping to achieve by being rich?"),   # was "by being you hope to be rich?"
    ("02", 0, (), "100% of my salary", "03", None),   # guard: an amount, not "for sure"
    # round 50
    ("goal_practical", 0, (), "sorry, quit", "goal_practical", "What would that actually change for you, day to day?"),   # ended the call
    ("goal_practical", 0, (), "quit, what else", "goal_practical", "What would that actually change for you, day to day?"),
    ("goal_practical", 0, (), "well, quit", "goal_practical", "What would that actually change for you, day to day?"),
    ("01", 0, (), "money, wait no, time", "goal_practical", "What are you hoping to achieve with time?"),   # was said back whole
    ("01", 0, (), "money because bills", "goal_practical", "What are you hoping that would get you?"),   # was "What do you mean by money?"
    ("01", 0, (), "money because of bills", "goal_identity", None),   # guard: not a close call, as before
    ("03", 0, (), "a year, no, two", "04", "24 months... Damn."),   # was a bare "two", missed
    ("19", 0, (), "yy", "20", "What makes you say that?"),   # was unclear
    ("22", 0, (), "db", "end", "Perfect."),   # was unclear
    ("19", 0, (), "sorry, y", "20", "What makes you say that?"),   # was asked again: the bare "y" after a cut
    ("19", 0, (), "well, no", "19", None),   # guard: still a no
    # round 51
    ("18", 0, (), "ok", "19", "Do you see yourself jumping in?"),   # was unclear: torn between a yes and a no
    ("18", 0, (), "okk", "19", "Do you see yourself jumping in?"),
    ("willing", 0, (), "ok", "willing_check", None),   # was "What makes you so different": the check skipped
    ("goal_practical", 0, (), "quitt", "goal_practical", "What would that actually change for you, day to day?"),   # ended the call
    ("01", 0, (), "hi, money", "goal_practical", "What are you hoping that would get you?"),   # was "...with hi, money?"
    ("05", 0, (), "same", "05", None),   # was saved as the answer
    ("05", 0, (), "the usual", "05", None),
    ("05", 0, (), "so basically ok", "05", None),
    ("03", 0, (), "not a year, two", "04", "24 months... Damn."),   # was "12 months"
    ("03", 0, (), "a whole year", "04", "12 months... Damn."),   # said no number back
    ("19", 0, (), "not now, maybe later", "m_think_what", None),   # guard: a stall, the denied "now" is not cut off
    # round 52
    ("19", 0, (), "yes because I need the money", "20", "What makes you say that?"),   # was a money worry
    ("19", 0, (), "yeah because my wife wants it", "20", "What makes you say that?"),   # was a partner worry
    ("19", 0, (), "yes cos I need it", "20", "What makes you say that?"),   # was unclear
    ("willing", 0, (), "yes because I want change", "willing_check", None),   # was a no
    ("willing", 0, (), "why not", "willing_check", None),   # was a no
    ("willing", 0, (), "ofc because I want change", "willing_check", None),   # a short form of yes, then a reason: was unclear
    ("willing", 0, (), "k because why not", "willing_check", None),   # was a no
    ("19", 0, (), "y because I need money", "20", "What makes you say that?"),   # was a money worry
    ("19", 0, (), "yh cos I need the money", "20", "What makes you say that?"),   # was unclear
    ("18", 0, (), "sound", "19", "Do you see yourself jumping in?"),   # was "let me say that again"
    ("20", 0, (), "sure because I trust you", "22", None),   # was a scam worry
    ("05", 0, (), "ok rn", "05", None),   # was saved as the answer
    ("01", 0, (), "more money rn", "goal_practical", "What are you hoping to achieve with more money?"),   # was "...more money rn?"
    ("01", 0, (), "£2k/month", "goal_practical", "What are you hoping to achieve with £2k a month?"),   # was "£2k month"
    ("01", 0, (), "also more money", "goal_practical", "What are you hoping to achieve with more money?"),   # was "...also more money?"
    ("19", 0, (), "no because I can't afford it", "m_funded", None),   # guard: a reason after a no is still the worry
    ("19", 0, (), "yes but I can't afford it", "m_funded", None),   # guard: so is one after "but"
    ("willing", 0, (), "n because I like my job", "11", None),   # guard: a short form of no stays a no
    # round 53
    ("20", 0, (), "fair enough", "20", None),   # was heard as paying at "Credit or debit?": "Welcome aboard"
    ("22", 0, (), "fair enough", "22", "Which works better for you, credit or debit?"),   # was "Welcome aboard"
    ("22", 0, (), "debit tbh", "end", None),   # guard: a way to pay still ends the call
    ("22", 0, (), "#debit", "end", None),
    ("05", 0, (), "ok if it works", "05", None),   # was saved as the answer
    ("05", 0, (), "ok damn", "05", None),   # was saved as the answer
    ("05", 0, (), "shore", "05", None),   # was saved as the answer
    ("18", 0, (), "shore", "19", "Do you see yourself jumping in?"),   # was unclear
    ("18", 0, (), "#ok", "19", "Do you see yourself jumping in?"),   # was unclear
    ("18", 0, (), "like ok", "19", "Do you see yourself jumping in?"),   # was "let me put it another way"
    ("01", 0, (), "like money", "goal_practical", None),   # was "let me put it another way"
    ("01", 0, (), "like what?", "01", "Fair point, let me put it another way."),   # guard: still asks what we mean
    ("01", 0, (), "to be fair money", "goal_practical", "What are you hoping that would get you?"),   # was "...by being fair money?"
    ("01", 0, (), "free tbh", "goal_practical", "What are you hoping to achieve by being free?"),   # guard: said back without its tag, as before
    # round 54
    ("05", 0, (), "well ok", "05", None),   # was saved as the answer
    ("05", 0, (), "actually ok", "05", None),   # was saved as the answer
    ("05", 0, (), "omg ok", "05", None),   # was saved as the answer
    ("18", 0, (), "omg ok", "19", "Do you see yourself jumping in?"),   # was unclear
    ("18", 0, (), "wow ok", "19", "Do you see yourself jumping in?"),   # was "let me put it another way"
    ("18", 0, (), "oh ok", "19", "Do you see yourself jumping in?"),   # was "let me put it another way"
    ("18", 0, (), "oh no", "18", None),   # guard: heard as a plain "no", as before
    ("01", 0, (), "actually money", "goal_practical", "What are you hoping that would get you?"),   # was "...with actually money?"
    ("01", 0, (), "well paid job", "goal_practical", "What are you hoping to achieve with well paid job?"),   # was "...with paid job?"
    ("01", 0, (), "free innit", "goal_practical", "What are you hoping to achieve by being free?"),   # could not be said back
    # round 55
    ("01", 0, (), "kinda free", "goal_practical", "What are you hoping to achieve by being free?"),   # was "...with kinda free?"
    ("01", 0, (), "free for real", "goal_practical", "What are you hoping to achieve by being free?"),   # was "...with free for real?"
    ("05", 0, (), "kinda ok", "05", None),   # was saved as the answer
    ("05", 0, (), "defo", "05", None),   # was saved as the answer
    ("05", 0, (), "cheers", "05", "You're welcome"),   # was saved as the answer
    ("18", 0, (), "deffo", "19", "Do you see yourself jumping in?"),   # was unclear
    ("18", 0, (), "for real", "18", "Put simply"),   # was "I'm an AI playing the salesperson"
    # round 56
    ("01", 0, (), "free sure", "goal_practical", "What are you hoping to achieve by being free?"),   # was "...with free sure?"
    ("05", 0, (), "yup", "05", None),   # was saved as the answer
    ("05", 0, (), "sure thing", "05", None),   # was saved as the answer
    ("05", 0, (), "ngl ok", "05", None),   # was saved as the answer
    ("05", 0, (), "as I said ok", "05", None),   # was saved as the answer
    ("06", 1, (), "ok please", "08", None),   # was "No problem, take your time."
    ("18", 0, (), "sure thing", "19", "Do you see yourself jumping in?"),   # guard: still a yes
    ("22", 0, (), "debit please", "end", None),   # guard: still pays
    # round 57
    ("01", 0, (), "let me see... money", "goal_practical", "What are you hoping that would get you?"),   # was "...with let you see?"
    ("01", 0, (), "money in a way", "goal_practical", "What are you hoping that would get you?"),   # was "...with money in a way?"
    ("01", 0, (), "quit proper", "goal_practical", "What are you hoping to achieve by being able to quit your job?"),   # was "...quit proper?"
    ("01", 0, (), "same as before", "01", "What are you actually hoping to achieve?"),   # was "let me say that again"
    ("goal_practical", 0, (), "same as before", "goal_practical", None),   # was saved as the answer
    ("05", 0, (), "erm ok", "05", None),   # was saved as the answer
    ("05", 0, (), "you know what, ok", "05", None),   # was saved as the answer
    ("05", 0, (), "let me see", "05", "No rush"),   # was heard as leaving: the call ended
    ("05", 0, (), "lemme see", "05", "No rush"),   # was heard as leaving
    ("05", 0, (), "let me think about it", "05", "No rush"),   # was "What do you mean by let you think about it?"
    ("18", 0, (), "let me see the price", "18", "Put simply"),   # guard: no break, nothing cut
    ("19", 0, (), "see you", "later", None),   # guard: still leaving
    # round 58
    ("01", 0, (), "money or whatever", "goal_practical", "What are you hoping that would get you?"),   # was "...with money or?"
    ("01", 0, (), "literally money", "goal_practical", "What are you hoping that would get you?"),   # was "...with literally money?"
    ("01", 0, (), "money if that makes sense", "goal_practical", "What are you hoping that would get you?"),
    ("01", 0, (), "free or whatever", "goal_practical", "What are you hoping to achieve by being free?"),   # was asked again
    ("01", 0, (), "probably money", "goal_practical", "What are you hoping that would get you?"),   # was "What do you mean by money?"
    ("05", 0, (), "I guess money", "06", None),   # was "What do you mean by money?"
    ("05", 0, (), "ok stuff like that", "05", "No rush"),   # was "let me say that again", at every step
    ("05", 0, (), "perhaps", "05", "No rush"),   # was "What do you mean by perhaps?"
    ("05", 0, (), "probably ok", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "literally ok", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok if that makes sense", "05", "No rush"),   # was saved as the answer
    ("22", 0, (), "dbt", "end", None),   # was asked again
    ("01", 0, (), "I guess I want a side income", "goal_practical", "What are you hoping to achieve with a side income?"),   # was "What
    ("01", 0, (), "I want passive income", "goal_practical", "What are you hoping to achieve with passive income?"),   # do you mean by"
    ("01", 0, (), "maybe later", "01", "That's fair"),   # guard: "maybe" is not split off
    ("19", 0, (), "probably not", "19", None),   # guard: the hedge is the answer
    ("19", 0, (), "yes I reckon", "20", "What makes you say that?"),   # guard: still a yes
    # round 59
    ("22", 0, (), "ok ideally", "22", "Which works better"),   # was heard as paying: "Welcome aboard"
    ("20", 0, (), "ok ideally", "20", "No rush"),   # was saved, then heard as paying at 22
    ("18", 0, (), "ok :)", "19", "Do you see yourself"),   # was "You're welcome"
    ("18", 0, (), "ok big time", "19", "Do you see yourself"),   # was "You're welcome"
    ("willing", 0, (), "ok tho", "willing_check", None),   # was a no
    ("willing", 0, (), "ok mainly", "willing_check", None),   # was a no
    ("01", 0, (), "money tho", "goal_practical", "What are you hoping that would get you?"),   # was "...with money tho?"
    ("01", 0, (), "ideally money", "goal_practical", "What are you hoping that would get you?"),   # was "...with ideally money?"
    ("01", 0, (), "anyway, money", "goal_practical", "What are you hoping that would get you?"),   # was "...with anyway, money?"
    ("05", 0, (), "ok tho", "05", "No rush"),   # was saved as the answer
    ("22", 0, (), "ideally debit", "end", None),   # guard: still pays
    ("willing", 0, (), "no tho", "11", None),   # guard: still a no
    # round 60
    ("05", 0, (), "obviously ok", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok pretty much", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok more or less", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "lowkey ok", "05", "No rush"),   # was saved as the answer
    ("01", 0, (), "money pretty much", "goal_practical", "What are you hoping that would get you?"),   # was "...with money pretty much?"
    ("01", 0, (), "seriously money", "goal_practical", "What are you hoping that would get you?"),   # was "...with seriously money?"
    ("01", 0, (), "money for now", "goal_practical", "What are you hoping that would get you?"),   # was "...with money for now?"
    ("01", 0, (), "money to me", "goal_practical", "What are you hoping that would get you?"),   # was "...with money to you?"
    ("18", 0, (), "ok basically", "19", "Do you see yourself"),   # was asked again
    ("20", 0, (), "obviously not", "19", "No pressure"),   # was unclear, then on to the payment
    ("20", 0, (), "not for now", "m_think_what", "Sure."),   # guard: still a "later"
    ("willing", 0, (), "really not", "11", None),   # guard: still a no
    # round 61
    ("05", 0, (), "true", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok kind of thing", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "essentially ok", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok as well", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok or anything", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "generally ok", "05", "No rush"),   # was saved as the answer
    ("01", 0, (), "money kind of thing", "goal_practical", "What are you hoping that would get you?"),   # was "...with money kind of thing?"
    ("01", 0, (), "true, money", "goal_practical", "What are you hoping that would get you?"),   # was "...with true, money?"
    ("01", 0, (), "money to start", "goal_practical", "What are you hoping that would get you?"),   # was "...with money to start?"
    ("01", 0, (), "money right now", "goal_practical", "What are you hoping that would get you?"),   # was "...with money right now?"
    ("01", 0, (), "true freedom", "goal_practical", "What are you hoping to achieve with true freedom?"),   # guard: "true" is theirs
    ("willing", 0, (), "true", "willing_check", None),   # guard: still a yes
    # round 62
    ("05", 0, (), "ok etc", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok innit", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "frankly ok", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "bruh ok", "05", "No rush"),   # was saved as the answer
    ("05", 0, (), "ok and whatnot", "05", "No rush"),   # was saved as the answer
    ("18", 0, (), "ok and so on", "19", "Do you see yourself"),   # was unclear
    ("18", 0, (), "ok etc", "19", "Do you see yourself"),   # was "let me put it another way"
    ("01", 0, (), "money etc", "goal_practical", "What are you hoping that would get you?"),   # was "...with money etc?"
    ("01", 0, (), "frankly money", "goal_practical", "What are you hoping that would get you?"),   # was "...with frankly money?"
    ("01", 0, (), "money no doubt", "goal_practical", "What are you hoping that would get you?"),   # was "...with money no doubt?"
    ("19", 0, (), "no doubt", "20", "What makes you say that?"),   # was heard as not yet
    ("19", 0, (), "I doubt it", "19", None),   # guard: still not yet
    # round 63
    ("goal_practical", 0, (), "aye quit", "goal_practical", "What would that actually change"),   # was heard as leaving: the call ended
    ("01", 0, (), "aye money", "goal_practical", "What are you hoping that would get you?"),   # was "...with aye money?"
    ("01", 0, (), "money, if not more", "goal_practical", "What are you hoping that would get you?"),   # was "...with money, if not more?"
    ("01", 0, (), "money and then some", "goal_practical", "What are you hoping that would get you?"),   # was "...with money and then some?"
    ("willing", 0, (), "aye", "willing_check", None),   # guard: still a yes
    ("01", 0, (), "see ye", "later", "No problem."),   # guard: still a goodbye
    ("01", 0, (), "passive income streams", "goal_practical", "What are you hoping to achieve with passive income streams?"),   # round 58 mutation: no row had this
    # round 64
    ("goal_practical", 0, (), "who knows", "goal_practical", "What would that actually change"),   # was "What do you mean by who knows?"
    ("goal_practical", 0, (), "hard to say", "goal_practical", "What would that actually change"),   # was "What do you mean by hard to say?"
    ("goal_practical", 0, (), "beats me", "goal_practical", "What would that actually change"),   # was "What do you mean by beats you?"
    ("goal_practical", 0, (), "we'll see", "goal_practical", "What would that actually change"),   # was saved as the answer
    ("goal_practical", 0, (), "deadass", "goal_practical", "What would that actually change"),   # was saved as the answer
    ("goal_practical", 0, (), "ong", "goal_practical", "What would that actually change"),   # was saved as the answer
    ("01", 0, (), "money deadass", "goal_practical", "What are you hoping that would get you?"),   # was "...with money deadass?"
    ("01", 0, (), "money ong", "goal_practical", "What are you hoping that would get you?"),   # was "...with money ong?"
    ("goal_practical", 0, (), "stuff I guess", "goal_practical", "What do you mean by stuff?"),   # guard: words to ask about
    ("goal_practical", 0, (), "hard to say, my family", "goal_identity", None),   # guard: the answer after it
    # round 65
    ("01", 0, (), "money fingers crossed", "goal_practical", "What are you hoping that would get you?"),   # was "...with money fingers crossed?"
    ("01", 0, (), "money touch wood", "goal_practical", "What are you hoping that would get you?"),   # was "...with money touch wood?"
    ("goal_practical", 0, (), "fingers crossed", "goal_practical", "What would that actually change"),   # was saved as the answer
    ("goal_practical", 0, (), "you tell me", "goal_practical", "What would that actually change"),   # was saved as the answer
    ("goal_practical", 0, (), "aight", "goal_practical", "What would that actually change"),   # was saved as the answer
    ("05", 0, (), "up to you", "05", None),   # was heard as leaving, and the call ended
    ("20", 0, (), "I'd like to think so", "20", None),   # was "What specifically do you need to think over"
    ("20", 0, (), "I'd like to think about it", "m_think_what", None),   # guard: the real one
    ("goal_practical", 0, (), "who knows, stuff", "goal_practical", "What do you mean by stuff?"),   # round 65 mutation: was "...by who knows, stuff?"
    # round 66
    ("05", 0, (), "hand on heart", "05", None), ("05", 0, (), "if anything", "05", None),   # were saved as the reason
    ("05", 0, (), "I'm easy", "05", None), ("05", 0, (), "I don't mind", "05", None),
    ("05", 0, (), "my boss, hand on heart", "06", None),   # guard: an answer beside it
    ("19", 0, (), "cool beans", "20", None), ("19", 0, (), "sweet as", "20", None),   # were unclear
    ("19", 0, (), "either way", "19", "Is this something you can see yourself doing?"),   # was "Fair point, let me put it another way"
    ("01", 0, (), "money if anything", "goal_practical", "What are you hoping that would get you?"),   # was "achieve with money if anything?"
    ("06", 1, (), "hand on heart", "06", "No rush"), ("06", 1, (), "per se", "06", "No rush"),   # asked as yes-or-no: was saved as the answer
    ("06", 1, (), "yes, hand on heart", "08", None), ("06", 1, (), "yeah", "08", None),   # guard: these answer it
    # round 67
    ("18", 0, (), "you see", "18", "Put simply"), ("18", 0, (), "so to speak", "18", "Put simply"), ("18", 0, (), "as it were", "18", "Put simply"),   # were leaving, "let me say that again", "let me put it another way"
    ("goal_practical", 0, (), "you see", "goal_practical", "What would that actually change"),   # was leaving: the call ended
    ("01", 0, (), "so to speak", "01", "What are you actually hoping"), ("01", 0, (), "in a nutshell", "01", "What are you actually hoping"), ("01", 0, (), "tops", "01", "What are you actually hoping"),   # were "say that again", a goal, saved
    ("18", 0, (), "obviously", "19", None), ("18", 0, (), "ok", "19", None), ("18", 0, (), "no worries", "19", None),   # guard: these say yes
    ("19", 0, (), "spot on", "20", None), ("19", 0, (), "bang on", "20", None),   # were unclear and "take your time"
    ("02", 0, (), "2k tops", "03", None), ("03", 0, (), "at least a year", "04", None),   # guard: the answer is kept
    # round 68
    ("18", 0, (), "by and large", "18", "Put simply"),   # was a money worry: "Tell me if you did have the funding"
    ("18", 0, (), "if you ask me", "18", "Put simply"), ("18", 0, (), "in short", "18", "Put simply"),   # were "Fair point, let me put it another way"
    ("01", 0, (), "as such", "01", "What are you actually hoping"), ("01", 0, (), "all in all", "01", "What are you actually hoping"),
    ("05", 0, (), "let's say", "05", "No rush"), ("05", 0, (), "needless to say", "05", "No rush"),   # were "let me say that again" and saved as the answer
    ("18", 0, (), "lovely", "19", None),   # was unclear
    ("05", 0, (), "correct", "05", "No rush"),   # round 68 mutation: was saved as the answer; "that's right" already said nothing
    ("18", 0, (), "by and large, the money", "m_funded", None), ("19", 0, (), "correct", "20", None), ("03", 0, (), "let's say a year", "04", None),   # guard: these still say it
    # round 69
    ("goal_practical", 0, (), "to some extent", "goal_practical", "What would that actually change"), ("goal_practical", 0, (), "on the whole", "goal_practical", "What would that actually change"),   # were "let me put it another way" and saved
    ("05", 0, (), "to some extent", "05", "No rush"), ("05", 0, (), "admittedly", "05", "No rush"), ("05", 0, (), "roger that", "05", "No rush"),   # were "let me say that again" and saved as the answer
    ("18", 0, (), "to some extent", "18", "Put simply"), ("01", 0, (), "at any rate", "01", "What are you actually hoping"),   # were "let me put it another way" and a goal
    ("18", 0, (), "roger that", "19", None), ("19", 0, (), "deal", "20", None),   # were unclear
    ("18", 0, (), "righto", "19", None), ("19", 0, (), "indeed", "20", None), ("19", 0, (), "on the whole", "19", "Is this something"),   # guard: as before
    # round 70
    ("05", 0, (), "if that", "05", "No rush"), ("goal_practical", 0, (), "if that", "goal_practical", "What would that actually change"),   # were "let me say that again" at every step: the call never ended
    ("18", 0, (), "on balance", "18", "Put simply"), ("18", 0, (), "in any case", "18", "Put simply"),   # were "take your time" and "let me put it another way"
    ("05", 0, (), "in any case", "05", "No rush"), ("goal_practical", 0, (), "as a matter of fact", "goal_practical", "What would that actually change"),   # were saved as the answer
    ("05", 0, (), "sounds good", "05", "No rush"), ("05", 0, (), "you bet", "05", "No rush"),   # were saved as the reason
    ("19", 0, (), "works for me", "20", None), ("18", 0, (), "you bet", "19", None),   # were a scam worry and unclear
    ("18", 0, (), "sounds good", "19", None), ("18", 0, (), "simply put", "19", None), ("02", 0, (), "2k if that", "03", None),   # guard: as before
    # round 71
    ("05", 0, (), "and such", "05", "No rush"), ("goal_practical", 0, (), "and such", "goal_practical", "What would that actually change"),   # were "let me say that again" at every step: the call never ended
    ("05", 0, (), "real talk", "05", "No rush"), ("18", 0, (), "real talk", "18", "Put simply"),   # were "I'm an AI playing the salesperson"
    ("18", 0, (), "bottom line", "18", "Put simply"), ("18", 0, (), "that said", "18", "Put simply"), ("18", 0, (), "off the top of my head", "18", "Put simply"),   # were "say that again", "put it another way" and "think it over"
    ("05", 0, (), "for the record", "05", "No rush"), ("05", 0, (), "count me in", "05", "No rush"),   # were saved as the reason
    ("goal_practical", 0, (), "all good", "goal_practical", "What would that actually change"), ("18", 0, (), "count me in", "19", None), ("18", 0, (), "all good", "19", None),   # were "You're welcome" and unclear
    ("02", 0, (), "2k at most", "03", None), ("19", 0, (), "go for it", "20", None),   # guard: as before
    ("05", 0, (), "who knows?", "05", "No rush"), ("02", 0, (), "up to you?", "02", "If you had to put"), ("05", 0, (), "no idea?", "05", "No rush"),   # round 71 mutation: were "I don't know that one offhand" and "I'm the AI playing the salesperson"
    ("18", 0, (), "you tell me?", "18", "Put simply"), ("19", 0, (), "hard to say?", "19", "Is this something"),
    ("05", 0, (), "why?", "05", "It helps me see"), ("01", 0, (), "who knows, money?", "goal_practical", None),   # guard: a real question, and an answer with the shrug
    # round 72
    ("05", 0, (), "so to speak?", "05", "No rush"), ("12", 0, (), "by and large?", "12", "No rush"), ("20", 0, (), "that said?", "20", "No rush"),   # were "I don't know that one offhand"
    ("willing", 0, (), "that said?", "willing", "No pressure"), ("02", 0, (), "really?", "02", "If you had to put"),   # were "What makes you so different" and "I don't know that one offhand"
    ("05", 0, (), "so?", "05", "No rush"), ("19", 0, (), "yeah?", "20", None),   # guard: as before
    # round 73
    ("05", 0, (), "money yeah?", "06", None), ("02", 0, (), "no?", "02", "If you had to put"), ("05", 0, (), "yada yada", "05", "No rush"),   # were "I don't know that one offhand" and the next step
    ("02", 0, (), "come again? 2k", "03", None), ("19", 0, (), "touché", "20", None),   # were "Of course, let me say that again" with the 2k lost, and asked again
    ("02", 0, (), "2k right?", "03", None), ("05", 0, (), "a year methinks", "06", None), ("05", 0, (), "meh", "06", "Fair enough"), ("19", 0, (), "no biggie", "20", None),   # guard: as before
    ("02", 0, (), "come again?", "02", "Of course"), ("05", 0, (), "meh, whatever", "06", "Fair enough"), ("02", 0, (), "yes or no?", "02", None),   # guard: as before
    ("02", 0, (), "money. no?", "02", "If you had to put"), ("02", 0, (), "quit. nope?", "02", "If you had to put"),   # round 73 mutation: were "I don't know that one offhand" and "Fair question"
    ("02", 0, (), "can I go now? 2k", "later", "No problem"), ("02", 0, (), "say that again? money", "02", "Of course"),   # were "I don't know that one offhand": the words beside it hid the ask
    ("02", 0, (), "can we stop here?", "later", "No problem"), ("19", 0, (), "can we do this another time?", "later", "No problem"),   # were "I don't know that one offhand"
    ("05", 0, (), "how long is it. no?", "05", "It's a 6-month process"), ("19", 0, (), "hmm, yeah?", "20", None), ("19", 0, (), "can we do this", "20", None),   # guard: as before
    ("01", 0, (), "that's a tough one, a year", "goal_practical", "What are you hoping to achieve with a year"), ("01", 0, (), "erm a year erm", "goal_practical", "What are you hoping to achieve with a year"),   # round 74 callers: were asked again and said back as "a year erm"
    ("01", 0, (), "cheers for asking, money", "goal_practical", "What are you hoping that would get you"), ("01", 0, (), "thanks, 2k", "goal_practical", "What are you hoping to achieve with 2k"), ("01", 0, (), "thank you so much, money", "goal_practical", "What are you hoping that would get you"),   # were said back with the thanks
    ("01", 0, (), "one sec, money", "goal_practical", "What are you hoping that would get you"), ("01", 0, (), "brb, my boss", "goal_practical", "What are you hoping to achieve with your boss"), ("01", 0, (), "money, like", "goal_practical", "What are you hoping that would get you"),   # were "take your time", "with brb, my boss?" and "let me put it another way"
    ("05", 0, (), "cheers for asking", "05", "You're welcome"), ("05", 0, (), "nice of you to ask", "05", "You're welcome"), ("05", 0, (), "thanks mate", "05", "You're welcome"), ("05", 0, (), "thanks so much", "05", "You're welcome. What's the reason"),   # were kept as the answer ("much")
    ("01", 0, (), "thanks mate", "01", "You're welcome"), ("01", 0, (), "hang on my phone is dying", "01", "No problem, take your time"), ("05", 0, (), "one sec", "05", "No problem, take your time"), ("05", 0, (), "thank you", "05", "You're welcome"),   # guard: as before
    ("06", 0, (), "thanks but no thanks", "later", "No problem"), ("05", 0, (), "I don't know how to start", "06", None),   # guard: as before
    ("06", 1, (), "don't know", "06", "No rush"), ("06", 1, (), "that's a tough one", "06", "No rush"), ("06", 1, (), "nothing", "08", None),   # round 74 callers: to "Is there anything you've tried so far?" saved as what they do; guard: "nothing" answers it
    ("01", 0, (), "a year. or so", "goal_practical", "What are you hoping to achieve with a year?"), ("01", 0, (), "money. or so i think", "goal_practical", "What are you hoping that would get you"),   # round 75: a tag after a full stop was kept ("a year. or so" was unclear)
    ("01", 0, (), "2k and stuff", "goal_practical", "What are you hoping to achieve with 2k?"),   # guard: as before
    ("01", 0, (), "I'd have to say free", "goal_practical", "What are you hoping to achieve by being free?"), ("01", 0, (), "to answer your question, money", "goal_practical", "What are you hoping that would get you?"),   # round 76 callers: said back whole
    ("01", 0, (), "short answer: 2k", "goal_practical", "What are you hoping to achieve with 2k?"), ("01", 0, (), "so... 2k", "goal_practical", "What are you hoping to achieve with 2k?"),   # round 76 callers: said back with the lead, or not at all
    ("01", 0, (), "money?!", "01", "Fair point, let me put it another way."), ("01", 0, (), "a year (sorry)", "goal_practical", "What are you hoping to achieve with a year?"),   # round 76 callers: "I don't know that one offhand", asked again
    ("01", 0, (), "2k (mostly)", "goal_practical", "What are you hoping to achieve with 2k?"),   # guard: as before
    ("goal_practical", 0, (), "so, quit", "goal_practical", None), ("goal_practical", 0, (), "quit :(", "goal_practical", None),   # round 76 callers: once the "so" or the emoji went, "quit" was bare and ended the call
    ("18", 0, (), "y 🙂", "19", "Do you see yourself jumping in?"), ("18", 0, (), "k 🙂", "19", "Do you see yourself jumping in?"),   # round 76: a short form before a smiley was unclear
    ("22", 0, (), "send me the link", "end", "Perfect."), ("22", 0, (), "yes, send me the link", "end", "Perfect."), ("22", 0, (), "the link please", "end", "Perfect."),   # round 76 replay: were "What do you need to think over?" and the fallback
    ("22", 0, (), "send me some information", "m_think_what", None),   # guard: still research
    ("01", 0, (), "A: money", "goal_practical", "What are you hoping that would get you?"), ("05", 0, (), "a) not sure", "05", "No rush"), ("01", 0, (), "money x", "goal_practical", "What are you hoping that would get you?"),   # round 77 callers: were "with a money?", "What do you mean by a not?" and "with money x?"
    ("19", 0, (), "yes why?", "20", "It helps me see"), ("01", 0, (), "money why?", "goal_practical", "It helps me see"), ("19", 0, (), "how come?", "19", "It helps me see"),   # round 77 callers: were "I don't know that one offhand"
    ("01", 0, (), "a year", "goal_practical", "What are you hoping to achieve with a year?"), ("01", 0, (), "I don't know why", "01", None),   # guard: as before
    ("goal_practical", 0, (), "not sure?", "goal_practical", "What would that actually change"), ("05", 0, (), "not sure ?", "05", "No rush"),   # round 78 callers: were "let me say that again"
    ("20", 0, (), "no, no idea", "20", "No rush"), ("05", 0, (), "no, no idea", "05", "No rush"),   # round 78 callers: were backing out, and "no" saved as the reason
    ("05", 0, (), "n/a", "05", "No rush"), ("05", 0, (), "tbd", "05", "No rush"),   # round 78 callers: were saved as the reason
    ("goal_identity", 0, (), "gimme a sec, free", "02", None),   # round 78 callers: was "take your time", the "free" lost
    ("goal_practical", 0, (), "eh?", "goal_practical", "Fair point"), ("20", 0, (), "nah", "19", "No pressure"), ("goal_identity", 0, (), "gimme a sec", "goal_identity", "No problem, take your time."),   # guard: as before
    ("05", 0, (), "I don't know why?", "05", "No rush"), ("05", 0, (), "not sure why", "05", "No rush"), ("05", 0, (), "no idea why?", "05", "No rush"),   # round 78 mutation: were "It helps me see" (round 77's cut), the reason saved, and "I'll find out"
    ("22", 0, (), "payment link please", "end", "Perfect."),   # round 78: was "credit or debit?" again
    ("01", 0, (), "um so like money I guess", "goal_practical", "What are you hoping that would get you?"), ("01", 0, (), "so like freedom", "goal_practical", None),   # round 79 callers: were "let me put it another way"
    ("05", 0, (), "both", "05", "No rush"), ("05", 0, (), "like I said", "05", "No rush"), ("05", 0, (), "ditto", "05", "No rush"), ("05", 0, (), "what I said", "05", "No rush"),   # round 79 callers: were "let me say that again", or saved as the reason
    ("05", 0, (), "unsure", "05", "No rush"), ("05", 0, (), "I am uncertain", "05", "No rush"),   # round 79 callers: were "What do you mean by unsure?", and saved as the reason
    ("01", 0, (), "so like what?", "01", "Fair point"), ("05", 0, (), "a bit of both", "06", None),   # guard: as before
    ("goal_practical", 0, (), "😂 quit", "goal_practical", "What would that actually change"), ("goal_practical", 0, (), ":) quit", "goal_practical", "What would that actually change"),   # round 80 callers: left the call
    ("01", 0, (), "more um money", "goal_practical", "What are you hoping to achieve with more money?"),   # round 80 callers: was "with more um money?"
    ("01", 0, (), "lol what?", "01", "Fair point"), ("01", 0, (), "oh what?", "01", "Fair point"),   # round 80 callers: were "I don't know that one offhand"
    ("19", 0, (), "yes, are you human?", "20", "I'm an AI"), ("01", 0, (), "are you human?", "01", "I'm an AI"),   # round 80 callers: were "I'll find out", or no answer
    ("05", 0, (), "idj", "05", "No rush"), ("05", 0, (), "nit sure", "05", "No rush"),   # round 80 callers: saved as the reason
    ("05", 0, (), "not sure, you?", "05", "I'm the AI"), ("05", 0, (), "dunno, and you?", "05", "I'm the AI"),   # round 81 callers: were "No rush"
    ("goal_identity", 0, (), "you?", "goal_identity", "I'm the AI"), ("05", 0, (), "idk, u?", "05", "I'm the AI"),   # round 81 callers: were "No rush"
    ("05", 0, (), "yourself?", "05", "I'm the AI"),   # round 81 callers: was "I don't know that one offhand"
    ("05", 0, (), "not sure, you know?", "05", "No rush"), ("05", 0, (), "lol idk, money?", "06", None),   # guards: a tag, and an unsure answer
    ("02", 0, (), "give me a sec, 2k", "03", None), ("02", 0, (), "give me a second, 2k", "03", None),   # round 78 config mutation: pinned
    ("02", 0, (), "just a sec, 2k", "03", None),   # round 78 config mutation: was saved whole
    ("05", 0, (), "don't know why", "05", "No rush"), ("05", 0, (), "no clue why", "05", "No rush"),   # round 78 config mutation: pinned
    ("05", 0, (), "no clue why?", "05", "No rush"), ("05", 0, (), "dunno why?", "05", "No rush"), ("05", 0, (), "idk why?", "05", "No rush"),   # round 78 config mutation: were "It helps me see"
    ("05", 0, (), "i wonder why?", "05", None), ("05", 0, (), "kids thats why?", "06", None),   # round 78 config mutation: "i wonder" was saved; round 82: was "I don't know that one offhand"
    ("05", 0, (), "dunno why", "05", "No rush"), ("05", 0, (), "idk why", "05", "No rush"), ("05", 0, (), "dunno how", "05", "No rush"), ("05", 0, (), "i don't know how", "05", "No rush"),   # round 78 config mutation: were "What do you mean by why?"
    ("05", 0, (), "don't know how", "05", "No rush"),   # round 78 config mutation: was "let me say that again"
    ("goal_practical", 0, (), "hm?", "goal_practical", "What would that actually change"), ("goal_practical", 0, (), "hm", "goal_practical", "What would that actually change"),   # round 82: "hm" was saved as the answer
    ("goal_practical", 0, (), "confused?", "goal_practical", "Fair point"), ("goal_practical", 0, (), "i'm lost", "goal_practical", "Fair point"), ("goal_practical", 0, (), "you lost me", "goal_practical", "Fair point"),   # round 82: saved as the answer
    ("goal_practical", 0, (), "I lost my job", "goal_identity", None), ("05", 0, (), "feeling lost", "06", None),   # guards: lost something is an answer
    ("goal_identity", 0, (), "2 years, what about you?", "goal_identity", "I'm the AI"),   # round 81: was "I'll find out" (2 years answers nothing)
    ("goal_practical", 0, (), "2 years, is that normal?", "goal_practical", "There's no right answer"),   # round 81: was "I'll find out"
    ("05", 0, (), "2 years, what about you?", "06", "I'm the AI"), ("goal_identity", 0, (), "5k, are you a bot?", "goal_identity", "I'm an AI"),   # guards
    ("01", 0, (), "like what?", "01", "Fair point"), ("01", 0, (), "are you married?", "01", "I don't know that one"),   # guard: as before
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


def test_a_side_line_said_just_before_is_the_reminder():
    """Round 81 callers: "2k, is that enough?", then "a year, is that long?" each got "There's no right answer
    here, it's just about you." word for word, four turns in a row."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="goal_identity", slots={"outcome": "money"}))
    first, _ = seller.reply("free, does that make sense?")
    text, _ = seller.reply("2k, is that enough?")
    assert first.startswith("There's no right answer") and text.startswith("Like I said a moment ago."), text
    assert seller.state.slots.get("number") == "2k" and seller.state.step == "03", seller.state   # the answer still moves on
    text, _ = seller.reply("a year, is that long?")
    assert text.startswith("There's no right answer"), text   # not said just before: the line itself


def test_a_shrug_after_a_pause_is_no_answer():
    """Round 78 callers: "let me think" after "take your time" was saved as the answer."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="goal_identity"))
    seller.reply("gimme a sec")
    text, _ = seller.reply("lemme think")
    assert seller.state.step == "goal_identity" and "identity" not in seller.state.slots, text
    seller.reply("free")
    assert seller.state.slots.get("identity") == "free", seller.state.slots
    seller.reset(ScriptState(step="05"))
    seller.reply("brb")
    text, _ = seller.reply("okay")
    assert text.startswith("No worries.") and "blocker" not in seller.state.slots, text   # was saved as the reason
    seller.reset(ScriptState(step="05"))
    seller.reply("brb")
    text, _ = seller.reply("not sure")
    assert text.startswith("No rush"), text   # round 78 mutation: a shrug after a pause is no answer, not "I'm back"


def test_a_second_thank_you_is_heard_as_the_rest():
    """Round 27 callers: "ok, thank you" again got "What do you mean by thank you?" and "Like I said"."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="05"))
    first, _ = seller.reply("ok, thank you")
    assert "You're welcome." in first, first
    step = seller.state.step
    second, _ = seller.reply("ok, thank you")
    assert "You're welcome." not in second and "Like I said" not in second and "What do you mean" not in second, second
    assert seller.state.step != step or second, (step, second)


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


def test_still_scared_after_the_yes_goes_back_to_the_soft_close():
    """Round 19: "I'm scared" to "What makes you say that?" was asked again forever (no way out of step 20)."""
    from core.buy_mode.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="20", raised=("fear",)))
    for _ in range(3):
        text, _ = seller.reply("I'm scared")
    assert seller.state.step == "19" and text == "Do you see yourself jumping in?", text


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
