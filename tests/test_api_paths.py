"""Each mode answers on its own path: /api/buy and /api/sell. Old paths are gone."""
import pytest

from backend.app import app
from core.providers.base import LLMResponse

BUY_PRODUCT = "high_ticket_sales_mentorship"  # a scripted product in selling.yaml


class StubBuyerProvider:
    provider_name = "stub"

    def is_available(self):
        return True

    def get_model_name(self):
        return "stub-model"

    def chat(self, messages, temperature=0.7, max_tokens=150):
        return LLMResponse(content="Can you tell me a bit more about that?")


@pytest.fixture
def client(monkeypatch):
    # buy mode: the offline test provider; sell mode: a stub buyer.
    monkeypatch.setattr("backend.routes.buy.validate_provider", lambda data: ("dummy", None))
    monkeypatch.setattr(
        "core.services.provider_router.create_provider",
        lambda *_args, **_kwargs: StubBuyerProvider(),
    )
    app.config["TESTING"] = True
    return app.test_client()


def test_buy_mode_answers(client):
    started = client.post("/api/buy/init", json={"product_type": BUY_PRODUCT})
    assert started.status_code == 200, started.get_json()
    headers = {"X-Session-ID": started.get_json()["session_id"]}

    replied = client.post("/api/buy/chat", json={"message": "I want more freedom"}, headers=headers)
    assert replied.status_code == 200, replied.get_json()
    assert replied.get_json()["message"]

    asked = client.get("/api/buy/quiz/question?type=stage", headers=headers)
    assert asked.status_code == 200, asked.get_json()
    assert asked.get_json()["type"] == "stage"


def test_sell_mode_answers(client):
    groups = client.get("/api/sell/product-groups")
    assert groups.status_code == 200
    assert set(groups.get_json()["groups"]) == {"transactional", "consultative"}

    started = client.post("/api/sell/init", json={"difficulty": "medium", "product_type": "default"})
    assert started.status_code == 200, started.get_json()
    headers = {"X-Session-ID": started.get_json()["session_id"]}

    replied = client.post("/api/sell/chat", json={"message": "What matters most to you?"}, headers=headers)
    assert replied.status_code == 200, replied.get_json()
    assert replied.get_json()["message"]


@pytest.mark.parametrize("old", ["/api/init", "/api/chat", "/api/test/question", "/api/prospect/init"])
def test_old_paths_are_gone(client, old):
    # Nothing answers: 404, or 405 from the page catch-all, which only takes GET.
    assert client.post(old, json={}).status_code in (404, 405)
