"""Sell-mode routes (/api/sell): starting a session, the product picker, and the session contract."""
import pytest

from backend.messages import SELL_SESSION_NOT_FOUND
from core.loader import load_buyer_config, load_buyer_products


def test_sell_init_returns_opening_message_and_history(sell_client):
    response = sell_client.post("/api/sell/init", json={"difficulty": "easy", "product_type": "default"})

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    # The opening line is filled from config, not written by the AI.
    opening = payload["message"]
    assert opening != "Can you tell me a bit more about that?"
    assert payload["persona"]["name"] in opening

    state_response = sell_client.get("/api/sell/state", headers={"X-Session-ID": payload["session_id"]})
    state_payload = state_response.get_json()

    assert state_response.status_code == 200
    assert state_payload["conversation_history"] == [{"role": "assistant", "content": opening}]


def test_sell_init_uses_the_default_difficulty_when_none_is_given(sell_client):
    payload = sell_client.post("/api/sell/init", json={"product_type": "default"}).get_json()

    assert payload["difficulty"] == load_buyer_config()["default_difficulty"]


def test_product_groups_split_transactional_and_consultative(sell_client):
    response = sell_client.get("/api/sell/product-groups")
    body = response.get_json()

    assert response.status_code == 200
    labels = {g: [o["label"] for o in opts] for g, opts in body["groups"].items()}
    assert set(labels) == {"transactional", "consultative"}
    assert "High-Ticket Sales Mentorship" in labels["consultative"]
    assert "Business Software" in labels["consultative"]
    all_labels = labels["transactional"] + labels["consultative"]
    assert len(all_labels) == len(set(all_labels)), "a product is listed twice"


def test_every_product_with_personas_can_be_picked(sell_client):
    groups = sell_client.get("/api/sell/product-groups").get_json()["groups"]
    picked = {option["id"] for options in groups.values() for option in options}
    products = load_buyer_products()["products"]

    with_personas = {p for p in load_buyer_config()["personas"] if p in products and p != "default"}

    assert with_personas <= picked


def test_sell_init_supports_high_ticket_sales_mentorship(sell_client):
    response = sell_client.post(
        "/api/sell/init", json={"difficulty": "easy", "product_type": "high_ticket_sales_mentorship"}
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["product_type"] == "high_ticket_sales_mentorship"
    assert payload["persona"]["name"] == "Ava"


def test_learner_picks_the_buyer_and_the_objection_to_practise(sell_client):
    """Chosen persona is used; chosen objection comes in the buyer's first reply, after the answer."""
    names = [p["name"] for p in sell_client.get("/api/sell/personas?product_type=default").get_json()["personas"]]
    objection = "We signed a two-year deal with someone else last month."

    init = sell_client.post(
        "/api/sell/init",
        json={"difficulty": "easy", "product_type": "default", "persona": names[-1].upper(), "objection": objection},
    ).get_json()
    reply = sell_client.post(
        "/api/sell/chat",
        json={"message": "What made you take this call?"},
        headers={"X-Session-ID": init["session_id"]},
    ).get_json()

    assert init["persona"]["name"] == names[-1]
    assert reply["message"] == f"Can you tell me a bit more about that? {objection}"


def test_sell_init_rejects_unknown_persona_and_oversized_objection(sell_client):
    unknown = sell_client.post("/api/sell/init", json={"persona": "Nobody"})
    too_long = sell_client.post("/api/sell/init", json={"objection": "x" * 201})
    wrong_type = sell_client.post("/api/sell/init", json={"objection": ["list"]})

    assert unknown.status_code == 400
    assert too_long.status_code == 400
    assert wrong_type.status_code == 400


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/api/sell/chat"),
        ("get", "/api/sell/state"),
        ("post", "/api/sell/evaluate"),
        ("get", "/api/sell/review"),
        ("get", "/api/sell/quiz"),
        ("post", "/api/sell/quiz"),
        ("post", "/api/sell/redo"),
    ],
)
def test_every_session_route_answers_a_dead_session_the_same_way(sell_client, method, path):
    """Sessions live in memory only; the web app starts over on code == SESSION_EXPIRED."""
    kwargs = {"headers": {"X-Session-ID": "a" * 32}}
    if method == "post":
        kwargs["json"] = {"message": "Hi", "turn": 1, "answer": "x"}

    response = getattr(sell_client, method)(path, **kwargs)

    assert response.status_code == 400
    assert response.get_json() == {"error": SELL_SESSION_NOT_FOUND, "code": "SESSION_EXPIRED"}
