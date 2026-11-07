"""The `reask` lead ("No rush, even a rough idea helps.") only goes in front of a question asked again,
never twice, and a saved call carries on after a JSON round trip."""
import json
from itertools import pairwise
from dataclasses import replace

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
