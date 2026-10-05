"""Tests for prospect session API contract and behavior."""
from backend.app import app
from backend.messages import PROSPECT_SESSION_NOT_FOUND
from core.providers.base import LLMResponse


class StubProspectProvider:
    def is_available(self):
        return True

    provider_name = "stub"

    def get_model_name(self):
        return "stub-model"

    def chat(self, messages, temperature=0.7, max_tokens=150):
        last_message = messages[-1]["content"]
        if "Start the conversation naturally" in last_message:
            return LLMResponse(content="Hi, I'm Alex. I'm looking into options today.")
        return LLMResponse(content="Can you tell me a bit more about that?")


def test_prospect_init_returns_opening_message_and_history(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setattr(
        "core.services.provider_router.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )

    response = client.post(
        "/api/prospect/init",
        json={"difficulty": "easy", "product_type": "default"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    # The opening line is filled from config, not written by the AI.
    opening = payload["message"]
    assert opening != "Hi, I'm Alex. I'm looking into options today."
    assert payload["persona"]["name"] in opening

    state_response = client.get(
        "/api/prospect/state",
        headers={"X-Session-ID": payload["session_id"]},
    )
    state_payload = state_response.get_json()

    assert state_response.status_code == 200
    assert state_payload["success"] is True
    assert state_payload["conversation_history"] == [
        {"role": "assistant", "content": opening}
    ]



def test_product_groups_split_transactional_and_consultative():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/prospect/product-groups")
    body = response.get_json()

    assert response.status_code == 200
    assert body["success"] is True
    labels = {g: [o["label"] for o in opts] for g, opts in body["groups"].items()}
    assert set(labels) == {"transactional", "consultative"}
    assert "High-Ticket Sales Mentorship" in labels["consultative"]
    assert "Business Software" in labels["consultative"]
    all_labels = labels["transactional"] + labels["consultative"]
    assert "Home Services & Renovation" not in all_labels
    assert len(all_labels) == len(set(all_labels)), "a product is listed twice"


def test_prospect_init_supports_high_ticket_sales_mentorship(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setattr(
        "core.services.provider_router.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )

    response = client.post(
        "/api/prospect/init",
        json={"difficulty": "easy", "product_type": "high_ticket_sales_mentorship"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["product_type"] == "high_ticket_sales_mentorship"
    assert payload["persona"]["name"] == "Ava"


def test_missing_prospect_session_returns_expired_contract():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get(
        "/api/prospect/state",
        headers={"X-Session-ID": "missingprospectsession123"},
    )
    payload = response.get_json()

    assert response.status_code == 400
    assert payload == {
        "error": PROSPECT_SESSION_NOT_FOUND,
        "code": "SESSION_EXPIRED",
    }


def _stub(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr(
        "core.services.provider_router.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )
    return app.test_client()


def test_learner_picks_the_buyer_and_the_objection_to_practise(monkeypatch):
    """Chosen persona is used; chosen objection comes in the buyer's first reply, after the answer."""
    client = _stub(monkeypatch)
    names = [p["name"] for p in client.get("/api/prospect/personas?product_type=default").get_json()["personas"]]
    objection = "We signed a two-year deal with someone else last month."

    init = client.post(
        "/api/prospect/init",
        json={"difficulty": "easy", "product_type": "default", "persona": names[-1].upper(), "objection": objection},
    ).get_json()
    reply = client.post(
        "/api/prospect/chat",
        json={"message": "What made you take this call?"},
        headers={"X-Session-ID": init["session_id"]},
    ).get_json()

    assert init["persona"]["name"] == names[-1]
    assert reply["message"] == f"Can you tell me a bit more about that? {objection}"


def test_prospect_init_rejects_unknown_persona_and_oversized_objection(monkeypatch):
    client = _stub(monkeypatch)

    unknown = client.post("/api/prospect/init", json={"persona": "Nobody"})
    too_long = client.post("/api/prospect/init", json={"objection": "x" * 201})
    wrong_type = client.post("/api/prospect/init", json={"objection": ["list"]})

    assert unknown.status_code == 400
    assert too_long.status_code == 400
    assert wrong_type.status_code == 400
