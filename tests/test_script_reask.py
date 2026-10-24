"""The `reask` lead ("No rush, even a rough idea helps.") only goes in front of a question asked again,
never twice, and a saved call carries on after a JSON round trip."""
import json

from core.loader import load_yaml
from core.script_engine.engine import ScriptState, _ask_again, ask_again
from core.script_engine.method import load_common_sense, load_method, load_offer
from core.script_engine.seller import ScriptSeller

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
    s = seller(fake_embedder, "08")
    said = [s.reply(r)[0] for r in ("yeah", "sure", "ok")]
    assert [leads(t) for t in said] == [[lead] for lead in CAT.reask]


def test_yes_is_a_shrug_to_an_open_question(fake_embedder):
    s = seller(fake_embedder, "09")
    s.reply("yes")
    assert s.state.step == "09" and s.state.asks == 1


def test_yes_answers_a_yes_or_no_question(fake_embedder):
    s = seller(fake_embedder, "06")
    s.reply("idk")  # 06's probe: "Is there anything you've tried so far ...?"
    s.reply("yes")
    assert s.state.step != "06"
