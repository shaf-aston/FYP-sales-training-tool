"""The real embedder against the public labelled replies. Opt-in (downloads a model)."""
import os
import statistics
import time
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from core.loader import load_yaml
from core.script_engine.embedder import make_embedder
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.recognise import Listener

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
    from core.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    for text in replies:
        seller.reply(text)
    assert seller.state.step == expected_step


def test_real_price_question_still_gets_the_early_answer():
    from core.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    seller = ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                          make_embedder(cfg, ROOT), _down)
    seller.reply("I want freedom")
    text, _ = seller.reply("wait, sorry, what's this going to cost me?")
    early = (seller.offer.facts["price"].answer, seller.method.objections["money"].early)
    assert text.startswith(early) and seller.state.step == "goal_practical"


def _real_seller():
    from core.script_engine.seller import ScriptSeller

    cfg = load_yaml("script/engine.yaml")
    return ScriptSeller(cfg, load_method("cat"), load_offer(cfg["products"]["high_ticket_sales_mentorship"]["offer"]), load_common_sense(),
                        make_embedder(cfg, ROOT), _down)


@pytest.mark.parametrize("said", ["money is tight and I don't have time", "I'm scared it won't work for me"])
def test_open_question_takes_an_objection_shaped_reply_as_its_answer(said):
    # "What's the reason you haven't got there?" - "money is tight" IS the answer, not an objection
    from core.script_engine.engine import ScriptState

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
    from core.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step=step))
    text, _ = seller.reply(said)
    assert text.startswith(seller.method.objections["scam"].early) and seller.state.step == step


@pytest.mark.parametrize("said", ["this is taking too long", "can we hurry up"])
def test_hurrying_the_call_up_is_frustration_not_a_pause(said):
    from core.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="05"))
    assert seller.reply(said)[0].startswith(seller.sense.interruptions["frustrated"].reply)


@pytest.mark.parametrize("step", ["03", "04", "05", "18"])
def test_a_pause_is_a_pause_on_any_step(step):
    from core.script_engine.engine import ScriptState
    from core.script_engine.seller import ScriptSeller

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
    from core.script_engine.engine import ScriptState

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
    ("I just want to know the price", "objection:money"),
])
def test_before_the_price_short_answers_are_not_objections(reply, heard):
    from core.script_engine import seller as S
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
    from core.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="m_open_wallet"))
    seller.reply(said)
    assert seller.state.step == step


def test_a_scam_question_where_doubts_are_answers_is_the_scam_worry_not_a_bot_question():
    # live call: "is this a scam though?" at "what's stopping you" got "Yes, I'm an AI..."
    from core.script_engine.engine import ScriptState

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
    from core.script_engine.engine import ScriptState

    seller = _real_seller()
    seller.reset(ScriptState(step="goal_practical", slots={"outcome": "more money"}))
    text, _ = seller.reply(said)
    assert text.startswith(seller.sense.interruptions["clarify"].reply) == clarify
