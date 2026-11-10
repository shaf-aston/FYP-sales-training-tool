"""A scripted call through /api/buy/init, /api/buy/chat and /api/buy/edit (offline provider)."""
import pytest

SCRIPT_PRODUCT = "high_ticket_sales_mentorship"  # listed under `products:` in script/engine.yaml


def _init(client):
    response = client.post(
        "/api/buy/init", json={"product_type": SCRIPT_PRODUCT}
    )
    body = response.get_json()
    assert response.status_code == 200, body
    return body, {"X-Session-ID": body["session_id"]}


def _say(client, headers, text):
    response = client.post("/api/buy/chat", json={"message": text}, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_call_opens_with_the_script_and_follows_it(client):
    opened, headers = _init(client)
    # step 00 ({setter} from the offer) runs straight on into step 01's question
    assert opened["message"] == (
        "I believe you had a chat with our setter... I've read your application but I don't like to assume anything. "
        "What do you want to specifically achieve by making money online?"
    )
    # "freedom" is a level 1 goal: dug into with their own words (no AI), then levels 2 and 3, then 02
    assert _say(client, headers, "I want financial freedom")["message"] == (
        "What are you hoping to achieve with financial freedom?"
    )
    _say(client, headers, "so I can stop stressing every time I buy something")
    assert _say(client, headers, "I'd finally be proud of myself")["message"] == (
        "How much would you need to be making each month to have financial freedom?"
    )
    plain = _say(client, headers, "ten thousand a month")["message"]
    assert plain == "How long have you been thinking about this?"


def test_opening_question_is_the_intent_stage_not_the_problem(client):
    opened, headers = _init(client)
    assert opened["stage"].lower() == "intent"
    # a vague answer keeps digging on the same opening question
    assert _say(client, headers, "not sure really")["stage"].lower() == "intent"


def test_stage_comes_from_the_script_step(client):
    _, headers = _init(client)
    reply = _say(client, headers, "I want to be free from my 9-5 and work from anywhere")
    assert reply["stage"].lower() == "intent"   # still digging the goal
    _say(client, headers, "so I can stop stressing every time I buy something")
    reply = _say(client, headers, "I'd finally be proud of myself")
    assert reply["stage"].lower() == "logical"


def test_same_replies_give_the_same_call(client):
    def call():
        opened, headers = _init(client)
        lines = [opened["message"]]
        for text in ("I want financial freedom", "ten thousand a month", "three years"):
            lines.append(_say(client, headers, text)["message"])
        return lines

    assert call() == call()


def test_edit_rewinds_the_script_too(client):
    _, headers = _init(client)
    first = _say(client, headers, "I want financial freedom")["message"]
    _say(client, headers, "ten thousand a month")
    edited = client.post(
        "/api/buy/edit", json={"index": 1, "message": "I want financial freedom"}, headers=headers
    ).get_json()
    assert edited["message"] == first
    assert edited["history"][0]["role"] == "assistant"  # the opening greeting is kept
    assert edited["history"][1]["content"] == "I want financial freedom"
    assert len(edited["history"]) == 3


def test_slang_tag_is_not_a_product_question(client):
    # live: "you get me?" read as "what do you do" -> programme pitched at step 01
    _, headers = _init(client)
    reply = _say(client, headers, "Just want to make money bro, you get me?")["message"]
    assert "programme" not in reply


def test_init_without_product_runs_the_script(client):
    # live: the web UI never picks a product, so the CAT script never ran
    body = client.post("/api/buy/init", json={}).get_json()
    assert "making money online" in body["message"]


@pytest.mark.parametrize("product", ["financial_services", "luxury_cars"])
def test_a_product_with_no_script_gets_the_default_one(client, product):
    # buy mode is scripted only; an unscripted product never gets AI-written sales talk
    from backend.app import seller_sessions

    body = client.post("/api/buy/init", json={"product_type": product}).get_json()
    assert seller_sessions.get(body["session_id"]).product_type == SCRIPT_PRODUCT
    assert "making money online" in body["message"]


def test_vague_opening_answer_is_dug_into_not_deflected(client):
    _, headers = _init(client)
    text = _say(client, headers, "I want to make money online")["message"]
    assert "That's fair" not in text and text == "What do you mean by wanting to make money online?"
    text = _say(client, headers, "I don't know")["message"]  # a shrug: nothing to ask about, so a probe
    assert text == "What are you actually hoping to achieve?"


def test_a_vague_prospect_hears_new_questions_then_the_call_moves_on(client):
    _, headers = _init(client)
    said = [_say(client, headers, "more money")["message"] for _ in range(6)]
    assert said[0] == "What are you hoping to achieve with more money?"  # the formula, in their words
    moved = next(i for i, t in enumerate(said) if t.startswith("How much"))  # moves on with no canned "Fair enough."
    assert all(a != b for a, b in zip(said[:moved], said[1:moved]))  # never the same line twice in a row


def test_a_failed_past_attempt_is_acknowledged_before_going_on(client):
    _, headers = _init(client)
    _say(client, headers, "I want financial freedom")
    _say(client, headers, "so I can stop stressing every time I buy something")
    _say(client, headers, "I'd finally be proud of myself")
    _say(client, headers, "ten thousand a month")
    text = _say(client, headers, "I tried dropshipping and it failed")["message"]
    # still asked how long: the next line says "so many nights, months and years" as if they had told us
    assert text.startswith("Sorry to hear that") and text.endswith("Roughly, is it more like months, or a few years?")
    assert "why can't you just ignore it" in _say(client, headers, "about two years")["message"]


def test_a_product_can_run_its_own_method(client, monkeypatch):
    from core.infra.loader import load_yaml

    cfg = load_yaml("script/engine.yaml")
    cfg["products"][SCRIPT_PRODUCT]["method"] = "impact_formula"
    monkeypatch.setattr("core.buy_mode.script_engine.seller.engine_config", lambda: cfg)
    opened, _ = _init(client)
    assert opened["message"] == "What would you like help with first?"
