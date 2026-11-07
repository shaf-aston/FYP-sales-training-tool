"""The `reask` lead ("No rush, even a rough idea helps.") only goes in front of a question asked again,
never twice, and a saved call carries on after a JSON round trip."""
import json
from dataclasses import replace
from itertools import pairwise

import pytest

from core.buy_mode.script_engine.engine import (
    ScriptState,
    _ask_again,
    _limit,
    ask_again,
)
from core.buy_mode.script_engine.method import (
    load_common_sense,
    load_method,
    load_offer,
)
from core.buy_mode.script_engine.seller import ScriptSeller
from core.infra.loader import load_yaml

CFG = load_yaml("script/engine.yaml")
CAT = load_method("cat")


def _down(prompt, max_tokens):
    raise RuntimeError("AI off")


def seller(bow, step):
    s = ScriptSeller(CFG, CAT, load_offer("shay_coaching"), load_common_sense(), bow, _down)
    s.reset(ScriptState(step=step))
    return s


def leads(text):
    return [r for r in CAT.reask if r in text]


def test_a_closing_step_never_gets_a_reask_lead(fake_embedder):
    s = seller(fake_embedder, "later")
    for reply in ("ok thanks, bye", "cool", "right"):
        text, _ = s.reply(reply)
        assert not leads(text), text


def test_a_rephrase_has_one_lead_not_two(fake_embedder):
    s = seller(fake_embedder, "00")
    text, _ = s.reply("what do you mean?")
    assert not leads(text), text


def test_a_question_asked_again_past_its_probes_still_gets_the_lead():
    step = next(v for v in CAT.steps.values() if v.capture and v.probes and "?" in v.say)
    move = _ask_again(CAT, ScriptState(step=step.id, asks=len(step.probes)), step,
                      misses=len(step.probes) + 1)  # probes all used, one ask left
    assert move.ack in CAT.reask


def test_a_saved_call_carries_on_after_a_json_round_trip(fake_embedder):
    s = seller(fake_embedder, "01")
    s.reply("I want to make money online")
    s.restore(json.loads(json.dumps(s.snapshot())))
    assert isinstance(s.state.said, tuple) and isinstance(s.state.parked, tuple)
    s.reply("I want to make money")


def test_a_question_rephrased_for_a_sense_gets_no_reask_lead():
    """`ask_again` is said behind the sense's own reply ("Fair point, let me put it another way."):
    a reask lead too would be two leads in a row."""
    step = next(v for v in CAT.steps.values() if not v.probes and "?" in v.say and not v.run_on)
    assert ask_again(CAT, ScriptState(step=step.id)).ack == ""


def test_each_lead_is_said_once_a_step(fake_embedder):
    s = seller(fake_embedder, "09")
    said = [s.reply(r)[0] for r in ("yeah", "sure")]  # `misses` re-asks, then the step moves on
    assert [leads(t) for t in said] == [[lead] for lead in CAT.reask[:2]]


def test_yes_is_a_shrug_to_an_open_question(fake_embedder):
    s = seller(fake_embedder, "09")
    s.reply("yes")
    assert s.state.step == "09" and s.state.asks == 1


def test_yes_answers_a_yes_or_no_question(fake_embedder):
    s = seller(fake_embedder, "06")
    s.reply("idk")  # 06's probe: "Is there anything you've tried so far ...?"
    s.reply("yes")
    assert s.state.step != "06"


def test_a_step_asked_about_again_and_again_moves_on():
    """They ask what it means again and again ("not sure" to "Does that make sense?"): explained once more
    than a step is usually asked, then the call moves on (live: asked 13 times in a row)."""
    for step in CAT.steps.values():
        if not step.routes:
            continue
        state = ScriptState(step=step.id)
        for _ in range(_limit(step, 0) + 2):
            state = ask_again(CAT, state).state
            if state.step != step.id:
                break
        assert state.step != step.id, step.id


def test_not_sure_again_and_again_at_the_temp_check_moves_to_the_close(fake_embedder):
    s = seller(fake_embedder, "18")
    for _ in range(6):
        s.reply("what do you mean")
    assert s.state.step != "18"


def test_a_lead_line_is_said_at_most_lead_repeats_times_a_call(fake_embedder):
    """Live (simulated rude caller): "Fair enough, I'll keep this quick." 20 times in one call."""
    s = seller(fake_embedder, "01")
    quick = s.sense.interruptions["frustrated"].reply
    texts = [s.reply("this is stupid")[0] for _ in range(8)]
    assert sum(quick in t for t in texts) == CFG["lead_repeats"]
    assert all(t.strip() for t in texts)


def test_said_lead_lines_survive_a_json_round_trip(fake_embedder):
    s = seller(fake_embedder, "01")
    s.reply("this is stupid")
    s.restore(json.loads(json.dumps(s.snapshot())))
    assert isinstance(s.state.spoken, tuple) and s.state.spoken


def test_a_step_reached_a_third_time_books_the_follow_up():
    """Going round in circles (19 -> 20 -> 22 -> stuck -> 19 ...): the call ends on the follow-up."""
    from core.buy_mode.script_engine.engine import jump
    state = ScriptState(step="19")
    for _ in range(CAT.max_visits + 1):   # landed twice, then a third time
        state = jump(CAT, replace(state, step="20"), "19").state
    assert state.step == CAT.follow_up


def test_the_same_message_twice_in_a_row_moves_on(fake_embedder):
    """Once its leads are worn out, a step with no other words would say the very same message again."""
    s = seller(fake_embedder, "belief_origin")
    s.reset(ScriptState(step="belief_origin", spoken=tuple(CAT.reask) * CFG["lead_repeats"]))  # leads worn out
    texts = [s.reply("ok")[0] for _ in range(6)]
    assert all(a != b for a, b in pairwise(texts)), texts


def test_a_shrug_moves_on_where_the_next_line_answers_the_question():
    """08 is answered by its own ack ("What makes you successful as an employee..."): "yeah" moves on unsaved."""
    from core.buy_mode.script_engine.engine import advance
    step = next(v for v in CAT.steps.values() if v.shrug_moves_on)
    move = advance(CAT, ScriptState(step=step.id), None, "yeah", empty=True, misses=CFG["misses"])
    assert move.state.step != step.id and step.capture not in move.state.slots


def test_a_step_that_hears_no_also_hears_yes():
    """"yes" and "no" sit close in meaning: a step with only one of them heard a plain "yes" as "no"."""
    from core.infra.loader import load_yaml as load
    answers = load("script/answers.yaml")
    for name in ("cat", "impact_formula"):
        for step in load_method(name).steps.values():
            heard = [set(r.examples) for r in step.listen]
            hears = [any(set(answers[a]) <= h for h in heard) for a in ("yes", "no")]
            assert hears[0] == hears[1], (name, step.id)


def test_a_rephrase_with_no_other_words_left_never_promises_other_words(fake_embedder):
    """Carla (whole calls): "what do you mean?" got the probe; "I don't understand the question" then got
    "let me put it another way" and the very same question."""
    sense = load_common_sense()
    rephrase = sense.interruptions["clarify"].reply
    s = seller(fake_embedder, "01")
    first, _ = s.reply("what do you mean")
    second, _ = s.reply("I don't understand the question")
    assert first.startswith(rephrase)
    assert s.state.step == "01" and rephrase not in second and second.startswith(sense.same_words), second


def test_a_rephrase_that_moves_on_drops_its_lead(fake_embedder):
    sense = load_common_sense()
    s = seller(fake_embedder, "08")   # no other words: asked again once, then the same message would follow
    s.reply("what do you mean")
    assert s.state.step == "08"
    text, _ = s.reply("what do you mean")
    assert s.state.step != "08"
    assert not text.startswith((sense.interruptions["clarify"].reply, sense.same_words)), text


def test_carry_on_stays_once_more_only_when_asked_to():
    from core.buy_mode.script_engine.engine import carry_on
    step = CAT.steps["19"]   # a step with other words (a probe)
    at_limit = ScriptState(step="19", asks=_limit(step, CFG["misses"]))
    assert carry_on(CAT, at_limit, misses=CFG["misses"]).state.step != "19"
    assert carry_on(CAT, at_limit, stay=True, misses=CFG["misses"]).state.step == "19"
    assert carry_on(CAT, at_limit, rephrase=True, misses=CFG["misses"]).state.step == "19"


def test_a_worry_handled_starts_the_visit_count_again():
    """Review: a buyer who handled two worries and came back to pay was booked a follow-up (a third
    landing on the payment step is progress after each worry, not going round in circles)."""
    from core.buy_mode.script_engine.engine import jump, object_to
    pay = CAT.steps["22"].id
    state = ScriptState(step="19", seen=(pay,) * CAT.max_visits)
    state = object_to(CAT, state, "money", CFG["objection_entries"]).state
    assert state.step != CAT.follow_up and pay not in state.seen
    assert jump(CAT, state, pay).state.step == pay


def test_going_round_in_circles_without_a_worry_still_books_the_follow_up():
    from core.buy_mode.script_engine.engine import jump
    state = ScriptState(step="19", seen=("22",) * CAT.max_visits)
    assert jump(CAT, state, "22").state.step == CAT.follow_up


@pytest.mark.parametrize("step", ["12", "01", "05"])
@pytest.mark.parametrize("side", ["how much is it?", "how did you get my number?", "who are you?"])
def test_a_question_said_again_behind_a_side_reply_spends_an_ask(fake_embedder, step, side):
    """Sid: "do my research" then "not sure" twice heard the question a 4th time. A side reply that says the
    step's question again spends the same budget as an ask again: at most `misses` + 1 times a step."""
    from core.buy_mode.script_engine.engine import question_of
    s = seller(fake_embedder, step)
    asked = 1
    for reply in (side, "not sure", "not sure", "not sure"):
        before = s.state.step
        s.reply(reply)
        if before != step or s.state.step != step:
            break
        asked += 1 if (s.state.asks + s.state.resaid) else 0
    assert s.state.step != step and asked <= CFG["misses"] + 1, (asked, question_of(CAT.steps[step].say))


def test_the_ask_budget_counts_a_side_reply_and_resets_on_a_new_step():
    from core.buy_mode.script_engine.engine import asks_left, start
    state = ScriptState(step="12", resaid=1, asks=CFG["misses"] - 1)
    assert not asks_left(CAT, state, CFG["misses"])
    assert asks_left(CAT, replace(state, resaid=0), CFG["misses"])
    assert start(CAT).state.resaid == 0


def test_a_yes_or_no_question_asked_again_gets_a_yes_or_no_lead(fake_embedder):
    """"No rush, even a rough idea helps." in front of "Would that work for you?" asks for a guess nobody needs."""
    from core.buy_mode.script_engine.engine import Move
    s, sense = seller(fake_embedder, "m_funding_options"), load_common_sense()
    for turn, lead in enumerate(CAT.reask):
        move = Move("Would that work for you?", ScriptState(step="m_funding_options"), "", ack=lead)
        want = sense.yes_no_reask[turn] if turn < len(sense.yes_no_reask) else ""
        assert s._closed_lead(move).ack == want
    open_move = Move("What do you do?", ScriptState(step="01"), "", ack=CAT.reask[0])
    assert s._closed_lead(open_move).ack == CAT.reask[0]   # an open question keeps "No rush"
    fair = Move("Would that work for you?", ScriptState(step="m_funding_options"), "", ack="Fair enough.")
    assert s._closed_lead(fair).ack == "Fair enough."   # a route's own ack is never swapped
    assert set(sense.yes_no_reask) <= set(s._leads)   # worn out like any lead


def test_brb_twice_is_never_the_same_words_twice(fake_embedder):
    """Live (whole calls): "brb" three times got "No problem, take your time." three times."""
    s = seller(fake_embedder, "03")
    said = [s.reply("brb")[0] for _ in range(3)]
    assert said[1] == s.sense.wait_again and all(a != b for a, b in pairwise(said)), said
    assert s.state.waiting and s.state.step == "03"


def test_a_yes_to_keep_settling_is_checked_and_a_no_goes_on():
    """"yes definitely" to "Are you willing to keep settling?" is most likely "willing to change": checked."""
    from core.buy_mode.script_engine.engine import advance
    assert advance(CAT, ScriptState(step="willing"), "yes").state.step == "willing_check"
    assert advance(CAT, ScriptState(step="willing"), "no").state.step == "11"
    assert advance(CAT, ScriptState(step="willing_check"), None, "ready for a change").state.step == "11"


def test_two_lines_in_a_row_never_both_open_with_okay(fake_embedder):
    """Whole calls: "Okay." opened four owner lines in a row (m_reframe1, _now, _dictate)."""
    s = seller(fake_embedder, "m_reframe1")
    s.state = replace(s.state, last="Okay. So, I can understand that.")
    assert s._fresh_opener("Okay. And are you 100% with where you are at right now?") == \
        "And are you 100% with where you are at right now?"
    assert s._fresh_opener("Okay, And do you want that?") == "And do you want that?"
    assert s._fresh_opener("Okay.") == "Okay."   # nothing left: said as it is
    s.state = replace(s.state, last="Fair enough.")
    assert s._fresh_opener("Okay. And are you sure?") == "Okay. And are you sure?"


def _price_asks(s, n):
    return [s._fact("price", False)[0] for _ in range(n)]


def test_the_price_asked_again_and_again_gets_a_straight_answer_once(fake_embedder):
    """Whole calls: the price asked ~40 times before the pitch got the same holding line each time."""
    s = seller(fake_embedder, "01")
    fact = s.offer.facts["price"]
    said = _price_asks(s, 4)
    assert said[0] == s._filler.fill(fact.answer, {})
    assert said[2] == s._filler.fill(fact.pressed, {})
    assert "$5k" in said[2] and "$5k" in said[3] and said[3] != said[2]
    assert s._fact("price", True)[0] == s._filler.fill(fact.late_again, {})   # told: the pitch doesn't tell again


def test_the_price_after_the_pitch_is_the_late_answer_then_its_short_form(fake_embedder):
    s = seller(fake_embedder, "15")
    fact = s.offer.facts["price"]
    first, again = _price_asks_opened(s)
    assert first == s._filler.fill(fact.late_answer, {}) and again == s._filler.fill(fact.late_again, {})


def _price_asks_opened(s):
    return s._fact("price", True)[0], s._fact("price", True)[0]


def test_a_fact_with_no_pressed_line_is_never_pressed(fake_embedder):
    s = seller(fake_embedder, "01")
    name = next(k for k, f in s.offer.facts.items() if not f.pressed)
    said = [s._fact(name, False)[0] for _ in range(4)]
    assert f"{name}+" not in s.state.told and len(set(said[1:])) == 1, said


def test_a_shrug_with_suppose_or_mean_is_never_asked_about(fake_embedder):
    """Whole calls: "yeah I mean I suppose so, it depends really" was kept as an answer."""
    s = seller(fake_embedder, "05")
    text, _ = s.reply("yeah I mean I suppose so")
    assert s.last_turn["heard_as"] == "says_nothing" and "What do you mean by" not in text, text


def test_laughing_answers_no_yes_or_no_question(fake_embedder):
    """Whole calls: "lol" to "do you want that to dictate your results?" was heard as "no"."""
    for step in ("willing", "m_reframe1_dictate", "18"):
        s = seller(fake_embedder, step)
        s.reply("lol")
        assert s.state.step == step and s.last_turn["heard_as"] == "says_nothing", (step, s.last_turn)


def test_a_thumbs_up_is_not_blank(fake_embedder):
    s = seller(fake_embedder, "18")
    assert not s._ear._shrugs.blank("👍") and s._ear._shrugs.blank("lol hmm") and not s._ear._shrugs.blank("lol yes")


def test_okay_left_off_never_hides_a_word_for_word_repeat(fake_embedder):
    """The same question twice moves on; the opener is only left off what is finally said."""
    s = seller(fake_embedder, "m_reframe1_now")
    first, _ = s.reply("hmm")
    second, _ = s.reply("hmm")
    assert first != second, (first, second)


def test_a_question_of_vague_words_is_asked_not_shrugged(fake_embedder):
    """"anything?" asks something; "anything" alone says nothing."""
    s = seller(fake_embedder, "05")
    s.reply("anything?")
    assert s.last_turn["heard_as"] != "says_nothing", s.last_turn
    s = seller(fake_embedder, "05")
    s.reply("anything")
    assert s.last_turn["heard_as"] == "says_nothing", s.last_turn


def test_a_worry_parked_before_the_price_asked_again_gets_a_short_line(fake_embedder):
    """Whole calls: "how do I know this isn't a scam?" asked again before the price got "I'll find out"."""
    s = seller(fake_embedder, "04")
    name = next(k for k, o in s.method.objections.items() if o.early)
    first, again = s._park(name), s._park(name)
    assert first == s.method.objections[name].early and again == s.sense.park_again != first
    assert s.state.parked == (name,)


def test_a_worry_with_no_park_again_line_says_its_first_line_again(fake_embedder):
    s = seller(fake_embedder, "04")
    s.sense = replace(s.sense, park_again="")
    name = next(k for k, o in s.method.objections.items() if o.early)
    assert s._park(name) == s._park(name) == s.method.objections[name].early


def test_a_question_only_sense_said_as_a_statement_is_an_answer(fake_embedder):
    """`only_asked`: "does that matter?" asks why we ask; the same words said ("that does matter") answer the step."""
    asked = seller(fake_embedder, "05")
    asked.reply("does that matter?")
    said = seller(fake_embedder, "05")
    said.reply("that does matter")
    assert asked.last_turn["heard_as"] == "sense:why_ask" and said.last_turn["heard_as"] != "sense:why_ask", said.last_turn


@pytest.mark.parametrize("step, said, heard", [
    ("04", "I don't trust this", "answer"),                         # parked, said again before the price: an answer
    ("04", "how do I know this is legit?", "objection:scam"),       # asked again: still the worry
    ("15", "I don't trust this", "objection:scam"),                 # after the price: raised again, handled
])
def test_a_parked_worry_said_again(fake_embedder, step, said, heard):
    s = seller(fake_embedder, step)
    s.state = replace(s.state, parked=("scam",))
    s.reply(said)
    assert s.last_turn["heard_as"].startswith(heard), s.last_turn


def test_a_worry_asked_again_while_it_is_handled_answers_the_step(fake_embedder):
    """Whole calls: "how do I know this is legit?" in the scam talk got "I'll find out and let you know" 7 times."""
    s = seller(fake_embedder, "m_scam")
    s.state = replace(s.state, raised=("scam",))
    s.reply("how do I know this is legit?")
    assert s.last_turn["heard_as"].startswith("answer") and s.state.step == "m_scam", s.last_turn


def test_the_same_worry_parked_again_and_again_wears_its_line(fake_embedder):
    s = seller(fake_embedder, "09")
    assert s.sense.park_again in s._leads
    said = []
    for _ in range(4):
        s.state = replace(s.state, parked=("scam",), step="09", asks=0)
        said.append(s.reply("how do I know this is legit?")[0])
    assert [s.sense.park_again in t for t in said] == [True] * s.cfg["lead_repeats"] + [False] * (4 - s.cfg["lead_repeats"]), said


def test_an_answer_beside_a_handled_worry_asked_again_is_heard_whole(fake_embedder):
    """"find out, how do I know this is legit?" in the scam talk: one reply, never an answer with that question beside it."""
    s = seller(fake_embedder, "m_scam")
    s.state = replace(s.state, raised=("scam",))
    s.reply("find out, how do I know this is legit?")
    assert "+" not in s.last_turn["heard_as"] and s.last_turn["heard_as"].startswith("answer"), s.last_turn
