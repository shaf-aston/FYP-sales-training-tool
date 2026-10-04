"""Sessions must be counted at the end, not only at the start.

The log held 1,485 session_start events against 83 session_end, and no score was
ever recorded, so there was no evidence anyone ever finished a session or got
better at it.
"""

import pytest

from backend.app import app
from core.analytics.session_analytics import SessionAnalytics
from core.providers.base import LLMResponse


class StubProspectProvider:
    def is_available(self):
        return True

    provider_name = "stub"

    def get_model_name(self):
        return "stub-model"

    def chat(self, messages, temperature=0.7, max_tokens=150):
        return LLMResponse(content="Tell me more about that.")


@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr(
        "core.services.provider_router.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )
    return app.test_client()


def events_for(session_id, event):
    return [
        e
        for e in SessionAnalytics.get_session_analytics(session_id)
        if e.get("event_type") == event
    ]


@pytest.fixture
def played_session(client):
    started = client.post(
        "/api/prospect/init", json={"difficulty": "medium", "product_type": "default"}
    ).get_json()
    headers = {"X-Session-ID": started["session_id"]}
    client.post(
        "/api/prospect/chat",
        json={"message": "What made you start looking at this now?"},
        headers=headers,
    )
    return headers


def test_ending_a_prospect_session_is_recorded(client, played_session):
    session_id = played_session["X-Session-ID"]

    client.post("/api/prospect/reset", headers=played_session)

    ended = events_for(session_id, "session_end")
    assert len(ended) == 1
    assert ended[0]["engine"] == "prospect"
    assert ended[0]["outcome"] in {"active", "sold", "walked"}
    assert ended[0]["turn_count"] == 1
    assert "final_readiness" in ended[0]


def test_a_prospect_session_is_counted_at_the_start_too(client, played_session):
    """Ends are only meaningful next to starts from the same engine."""
    started = events_for(played_session["X-Session-ID"], "session_start")

    assert len(started) == 1
    assert started[0]["engine"] == "prospect"
    assert started[0]["difficulty"] == "medium"


def test_a_prospect_score_is_kept_not_just_shown(client, played_session):
    session_id = played_session["X-Session-ID"]

    response = client.post("/api/prospect/evaluate", headers=played_session)

    assert response.status_code == 200
    scored = events_for(session_id, "session_score")
    assert len(scored) == 1
    assert isinstance(scored[0]["total"], int)
    assert scored[0]["breakdown"]
    assert scored[0]["engine"] == "prospect"


def test_resetting_a_session_that_is_already_gone_records_nothing(client):
    """A stale id must not invent an ending for a session nobody played."""
    ghost = "b" * 32

    response = client.post("/api/prospect/reset", headers={"X-Session-ID": ghost})

    assert response.status_code == 200
    assert events_for(ghost, "session_end") == []


def test_ending_a_seller_bot_session_records_where_it_got_to():
    """Ending a session records the final stage reached."""
    from core.seller_bot import SellerBot

    class _Engine:
        current_stage = "DISCOVERY"
        flow_type = "consultative"
        user_turn_count = 4
        conversation_history = [{"role": "user"}, {"role": "assistant"}]

    bot = SellerBot.__new__(SellerBot)
    bot.session_id = "c" * 32
    bot.flow_engine = _Engine()
    bot.record_session_end()

    ended = events_for(bot.session_id, "session_end")
    assert len(ended) == 1
    assert ended[0]["final_stage"] == "DISCOVERY"
    assert ended[0]["turn_count"] == 4


def test_a_session_with_no_id_records_nothing():
    from core.seller_bot import SellerBot

    bot = SellerBot.__new__(SellerBot)
    bot.session_id = ""

    bot.record_session_end()  # must not raise

    assert events_for("", "session_end") == []
