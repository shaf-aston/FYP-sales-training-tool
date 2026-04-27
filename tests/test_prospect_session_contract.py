"""Tests for prospect session API contract and behavior."""
from backend.app import app
from backend.messages import PROSPECT_SESSION_NOT_FOUND
from core.providers.base import LLMResponse


class StubProspectProvider:
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
        "core.prospect_session.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )

    response = client.post(
        "/api/prospect/init",
        json={"difficulty": "easy", "product_type": "default"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] == "Hi, I'm Alex. I'm looking into options today."

    state_response = client.get(
        "/api/prospect/state",
        headers={"X-Session-ID": payload["session_id"]},
    )
    state_payload = state_response.get_json()

    assert state_response.status_code == 200
    assert state_payload["success"] is True
    assert state_payload["conversation_history"] == [
        {"role": "assistant", "content": "Hi, I'm Alex. I'm looking into options today."}
    ]


def test_prospect_products_are_curated_and_include_mentorship():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/prospect/products")
    payload = response.get_json()
    products = payload["products"]
    ids = {product["id"] for product in products}
    transactional_ids = {
        product["id"] for product in products if product["strategy"] == "transactional"
    }

    mentorship = next(
        product for product in products if product["id"] == "high_ticket_sales_mentorship"
    )

    assert response.status_code == 200
    assert len(transactional_ids) == 7
    assert "high_ticket_sales_mentorship" in ids
    assert mentorship["label"] == "High-Ticket Sales Mentorship"
    assert mentorship["strategy"] == "consultative"
    assert "real_estate" not in ids
    assert "budget_fragrances" not in ids
    assert "subscription_boxes" not in ids


def test_prospect_page_uses_separate_transactional_and_consultative_dropdowns():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/prospect")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'id="prospectTransactionalSelect"' in html
    assert 'id="prospectConsultativeSelect"' in html
    assert "Transactional products" in html
    assert "Consultative products" in html
    assert "High-Ticket Sales Mentorship" in html
    assert "Business Software" in html
    assert "Home Services & Renovation" not in html


def test_prospect_init_supports_high_ticket_sales_mentorship(monkeypatch):
    app.config["TESTING"] = True
    client = app.test_client()

    monkeypatch.setattr(
        "core.prospect_session.create_provider",
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
