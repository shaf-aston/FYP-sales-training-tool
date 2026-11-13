"""Jumping to a stage from the stage bar: the main step it lands on, the recap answers, the first line."""
import pytest

from core.buy_mode.script_engine.method import load_method, load_stage_jump
from test_script_scenarios import CAT, seller

STAGES = ["intent", "logical", "emotional", "pitch", "outcome"]


@pytest.mark.parametrize("name", ["cat", "impact_formula"])
def test_every_stage_starts_on_a_main_step_of_that_stage(name):
    method = load_method(name)
    starts = load_stage_jump()[name]["starts"]
    assert list(starts) == STAGES
    for stage, step_id in starts.items():
        step = method.steps[step_id]
        assert step.ui_stage == stage and step.say and step_id not in method.talks


@pytest.mark.parametrize("name", ["cat", "impact_formula"])
def test_every_answer_a_jump_skips_has_a_sample(name):
    method = load_method(name)
    samples = load_stage_jump()[name]["samples"]
    last = list(method.steps).index(load_stage_jump()[name]["starts"]["outcome"])
    captures = {s.capture for s in list(method.steps.values())[:last] if s.capture and s.id not in method.talks}
    assert captures <= set(samples)


def test_the_recap_lists_only_answers_before_the_stage(fake_embedder):
    starts = {s["stage"]: s for s in seller(fake_embedder).stage_starts()}
    assert starts["intent"]["recap"] == []
    assert [r["slot"] for r in starts["logical"]["recap"]] == ["outcome", "practical", "identity"]
    assert starts["logical"]["step"] == "02"


def test_a_jump_with_answers_builds_on_them(fake_embedder):
    s = seller(fake_embedder)
    text, stage = s.start_at("04", {"outcome": "financial freedom", "years": "about two years"})
    assert stage == "emotional"
    assert text.startswith("Picking up where we left off.")
    assert s.state.slots["outcome"] == "financial freedom"


def test_a_jump_without_answers_is_the_plain_line(fake_embedder):
    s = seller(fake_embedder)
    text, _ = s.start_at("04")
    assert not text.startswith("Picking up")
    assert s.state.slots == {}


def test_the_stage_starts_route_lists_where_each_stage_lands(live_seller):
    client, _seller, headers = live_seller
    res = client.get("/api/buy/stage-starts", headers=headers).get_json()
    assert res["stages"][0]["step"] == "02"


def test_the_jump_route_keeps_only_the_answers_the_recap_offered(live_seller):
    client, seller, headers = live_seller
    slots = {"outcome": "  more time with my kids ", "number": "1m a month", "junk": 5}
    res = client.post("/api/buy/jump", headers=headers, json={"step": "02", "slots": slots})
    assert res.status_code == 200 and res.get_json()["message"] == "line:02"
    assert seller.jumped == ("02", {"outcome": "more time with my kids"})


def test_the_jump_route_refuses_an_unknown_step(live_seller):
    client, _seller, headers = live_seller
    assert client.post("/api/buy/jump", headers=headers, json={"step": "zz"}).status_code == 400


@pytest.mark.parametrize("name", ["cat", "impact_formula"])
def test_every_sample_has_a_plain_label(name):
    cfg = load_stage_jump()[name]
    assert set(cfg["samples"]) == set(cfg["labels"])


# ---- sell mode: the learner is the rep, the AI buyer is the one who "said" the recap ----------------------

from core.sell_mode.buyer_state import select_persona
from core.training.stage_jump import sell_history, sell_stage_starts

ALEX = select_persona("general", "Alex")


def test_sell_recap_answers_are_the_personas_own_words():
    starts = {s["stage"]: s for s in sell_stage_starts(ALEX)}
    assert list(starts) == STAGES
    answers = {r["slot"]: r["answer"] for r in starts["emotional"]["recap"]}
    assert answers["goal"] == "Mainly efficiency improvement"
    assert answers["problem"] == "Honestly, current solution is slow"
    assert all("{" not in r["ask"] for s in starts.values() for r in s["recap"])


def test_sell_history_is_the_rep_asking_and_the_buyer_answering_ending_with_the_buyer():
    history = sell_history(ALEX, "logical", {"goal": "more sales", "junk": "x"})
    assert history == [{"role": "user", "content": "What would you like help with first?"},
                       {"role": "assistant", "content": "more sales"}]
    assert sell_history(ALEX, "intent", {}) == []
    with pytest.raises(ValueError):
        sell_history(ALEX, "nowhere", {})


def test_sell_stage_starts_route_names_the_buyer(sell_client):
    res = sell_client.get("/api/sell/stage-starts?product_type=default&persona=Alex").get_json()
    assert res["persona"] == "Alex" and [s["stage"] for s in res["stages"]] == STAGES
    assert sell_client.get("/api/sell/stage-starts?persona=Nobody").status_code == 400


def test_sell_jump_starts_on_the_call_so_far(sell_client):
    res = sell_client.post("/api/sell/init", json={"product_type": "default", "persona": "Alex",
                                                    "jump": {"stage": "logical", "answers": {"goal": "more sales"}}})
    body = res.get_json()
    assert res.status_code == 200
    assert [m["content"] for m in body["history"]] == ["What would you like help with first?", "more sales"]
    assert body["message"] == "more sales"


def test_sell_jump_to_an_unknown_stage_is_refused(sell_client):
    bad = sell_client.post("/api/sell/init", json={"persona": "Alex", "jump": {"stage": "nowhere"}})
    wrong = sell_client.post("/api/sell/init", json={"persona": "Alex", "jump": "pitch"})
    assert bad.status_code == 400 and wrong.status_code == 400
