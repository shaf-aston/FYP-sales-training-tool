"""Slice 5: a scripted call through /api/init, /api/chat and /api/edit (offline provider)."""
import pytest

from backend.app import app

SCRIPT_PRODUCT = "high_ticket_sales_mentorship"  # listed under `products:` in selling.yaml


@pytest.fixture
def client(scripted_selling, monkeypatch):
    # the route only lists real providers; the offline test provider is let through here
    monkeypatch.setattr("backend.routes.session.validate_provider", lambda data: ("dummy", None))
    app.config["TESTING"] = True
    return app.test_client()


def _init(client):
    response = client.post(
        "/api/init", json={"product_type": SCRIPT_PRODUCT}
    )
    body = response.get_json()
    assert response.status_code == 200, body
    return body, {"X-Session-ID": body["session_id"]}


def _say(client, headers, text):
    response = client.post("/api/chat", json={"message": text}, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_call_opens_with_the_script_and_follows_it(client):
    opened, headers = _init(client)
    # step 00 (plain line: no setter) runs straight on into step 01's question
    assert opened["message"] == (
        "I've read your application but I don't like to assume anything. "
        "What do you want to specifically achieve by making money online?"
    )
    # "freedom" is recognised, so the script moves to step 02. The dummy provider's blank
    # filler breaks the checks, so the plain script line is said.
    assert _say(client, headers, "I want financial freedom")["message"] == (
        "How much do you need to be making to feel that freedom?"
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
        "/api/edit", json={"index": 1, "message": "I want financial freedom"}, headers=headers
    ).get_json()
    assert edited["message"] == first
    assert edited["history"][0]["content"] == "I want financial freedom"


def test_init_without_product_runs_the_script(client):
    # live: the web UI never picks a product, so the CAT script never ran
    body = client.post("/api/init", json={}).get_json()
    assert "making money online" in body["message"]


@pytest.mark.parametrize("product", ["financial_services", "healthcare_services", "luxury_cars"])
def test_products_not_listed_never_get_the_coaching_script(client, product):
    # live: a Wealth Management trainee was pitched online-business coaching
    from backend.app import session_manager

    body = client.post("/api/init", json={"product_type": product}).get_json()
    bot = session_manager.get(body["session_id"])
    bot.flow_engine.switch_strategy("consultative")
    headers = {"X-Session-ID": body["session_id"]}
    reply = _say(client, headers, "I want a mentor to help me leave my job")["message"]
    assert bot.seller is None and "making money online" not in reply


def test_script_lines_reach_the_user_word_for_word(client, monkeypatch):
    from core.response_guardrails import Layer3CheckResult

    # the prompt-driven path's guardrail rewrites lines; scripted lines must never go through it
    monkeypatch.setattr(
        "core.seller_bot.apply_layer3_output_checks",
        lambda **kw: Layer3CheckResult(content="What should we focus on next?", was_corrected=True),
    )
    _, headers = _init(client)
    assert _say(client, headers, "I want financial freedom")["message"].startswith("How much")


def test_vague_opening_answer_is_dug_into_not_deflected(client):
    _, headers = _init(client)
    text = _say(client, headers, "I want to make money online")["message"]
    assert "That's fair" not in text and text == "What are you actually hoping to achieve?"


def test_a_failed_past_attempt_is_acknowledged_before_going_on(client):
    _, headers = _init(client)
    _say(client, headers, "I want financial freedom")
    _say(client, headers, "ten thousand a month")
    text = _say(client, headers, "I tried dropshipping and it failed")["message"]
    assert text.startswith("Sorry to hear that") and "why can't you just ignore it" in text


def test_a_product_can_run_its_own_method(client, monkeypatch):
    from core.loader import load_yaml

    cfg = load_yaml("selling.yaml")
    cfg["products"][SCRIPT_PRODUCT]["method"] = "impact_formula"
    monkeypatch.setattr("core.seller_bot.selling_config", lambda: {**cfg, "enabled": True})
    monkeypatch.setattr("core.script_engine.seller.selling_config", lambda: {**cfg, "enabled": True})
    opened, _ = _init(client)
    assert opened["message"] == "What would you like help with first?"
