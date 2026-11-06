"""The `reask` lead ("No rush, even a rough idea helps.") only goes in front of a question asked again,
never twice, and a saved call carries on after a JSON round trip."""
import json
from dataclasses import replace

from core.infra.loader import load_yaml
from core.buy_mode.script_engine.engine import ScriptState, _ask_again, _limit, ask_again
from core.buy_mode.script_engine.method import load_common_sense, load_method, load_offer
from core.buy_mode.script_engine.seller import ScriptSeller

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
    assert all(a != b for a, b in zip(texts, texts[1:])), texts


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
