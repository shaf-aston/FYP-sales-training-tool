"""Each mode answers on its new path (/api/buy, /api/sell) and on its old alias.

The old paths stay until the deployed web uses the new ones (backend/routes/old_paths.py).
"""
import pytest

from backend.app import app
from backend.routes.old_paths import OLD_BUY_PATHS, OLD_SELL_PREFIX
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


@pytest.mark.parametrize("init, chat, quiz", [
    ("/api/buy/init", "/api/buy/chat", "/api/buy/quiz/question"),
    ("/api/init", "/api/chat", "/api/test/question"),
])
def test_buy_mode_answers_on_new_and_old_paths(client, init, chat, quiz):
    started = client.post(init, json={"product_type": BUY_PRODUCT})
    assert started.status_code == 200, started.get_json()
    headers = {"X-Session-ID": started.get_json()["session_id"]}

    replied = client.post(chat, json={"message": "I want more freedom"}, headers=headers)
    assert replied.status_code == 200, replied.get_json()
    assert replied.get_json()["message"]

    asked = client.get(f"{quiz}?type=stage", headers=headers)
    assert asked.status_code == 200, asked.get_json()
    assert asked.get_json()["type"] == "stage"


@pytest.mark.parametrize("prefix", ["/api/sell", OLD_SELL_PREFIX])
def test_sell_mode_answers_on_new_and_old_paths(client, prefix):
    groups = client.get(f"{prefix}/product-groups")
    assert groups.status_code == 200
    assert set(groups.get_json()["groups"]) == {"transactional", "consultative"}

    started = client.post(f"{prefix}/init", json={"difficulty": "medium", "product_type": "default"})
    assert started.status_code == 200, started.get_json()
    headers = {"X-Session-ID": started.get_json()["session_id"]}

    replied = client.post(f"{prefix}/chat", json={"message": "What matters most to you?"}, headers=headers)
    assert replied.status_code == 200, replied.get_json()
    assert replied.get_json()["message"]


def test_a_session_started_on_an_old_path_carries_on_on_the_new_one(client):
    started = client.post("/api/prospect/init", json={"difficulty": "easy"}).get_json()
    headers = {"X-Session-ID": started["session_id"]}

    assert client.get("/api/sell/state", headers=headers).status_code == 200


def test_every_old_path_runs_the_same_view_as_its_new_path():
    """Same function, so rate limits, input checks and session lookup cannot drift."""
    rules = {rule.rule: rule for rule in app.url_map.iter_rules()}
    for old, new in OLD_BUY_PATHS.items():
        assert app.view_functions[rules[old].endpoint] is app.view_functions[rules[new].endpoint]
        assert rules[old].methods == rules[new].methods

    sell_rules = [r for r in app.url_map.iter_rules() if r.rule.startswith("/api/sell/")]
    assert sell_rules
    for rule in sell_rules:
        old = OLD_SELL_PREFIX + rule.rule.removeprefix("/api/sell")
        [twin] = [r for r in app.url_map.iter_rules() if r.rule == old and r.methods == rule.methods]
        assert app.view_functions[twin.endpoint] is app.view_functions[rule.endpoint]
