"""The logs a real chat leaves behind: events per session, and timings nested under each request."""
import pytest

from core.logs import SessionAnalytics, span

SCRIPT_PRODUCT = "high_ticket_sales_mentorship"


def test_a_buy_chat_leaves_its_events_and_nested_timings(client, logs):
    started = client.post("/api/buy/init", json={"product_type": SCRIPT_PRODUCT}).get_json()
    headers = {"X-Session-ID": started["session_id"]}

    reply = client.post("/api/buy/chat", json={"message": "I want financial freedom"}, headers=headers)

    assert reply.status_code == 200
    assert reply.headers["Server-Timing"].startswith("app;dur=")
    request_id = reply.headers["X-Request-ID"]

    turns = [e for e in logs("events") if e["event_type"] == "conversation_turn"]
    assert turns[-1]["session_id"] == started["session_id"]
    assert turns[-1]["user_message"] == "I want financial freedom"

    spans = [s for s in logs("timings") if s.get("request_id") == request_id]
    [request] = [s for s in spans if s["name"] == "request"]
    assert (request["route"], request["status"], request["depth"]) == ("POST /api/buy/chat", 200, 0)
    assert request["session_id"] == started["session_id"]
    turn = next(s for s in spans if s["name"] == "seller_bot.SellerBot.chat")
    assert (turn["parent"], turn["depth"]) == ("request", 1)
    assert all(s["ms"] >= 0 and s["ms"] <= request["ms"] for s in spans)


def test_a_step_that_fails_is_timed_as_failed_and_still_raises(logs):
    with pytest.raises(ValueError), span("broken step"):
        raise ValueError("boom")

    [timing] = logs("timings")
    assert (timing["name"], timing["ok"], timing["parent"]) == ("broken step", False, None)


def test_events_are_kept_per_session(analytics_events):
    SessionAnalytics.record(event="session_start", session_id="alpha", product_type="default")
    SessionAnalytics.record(event="session_end", session_id="alpha", turn_count=2)
    SessionAnalytics.record(event="session_start", session_id="beta")

    assert [e["event_type"] for e in analytics_events("alpha")] == ["session_start", "session_end"]
    assert analytics_events("alpha", "session_end")[0]["turn_count"] == 2
    assert len(analytics_events("beta")) == 1


def test_an_event_without_a_session_is_ignored(logs):
    SessionAnalytics.record(event="session_start", session_id="")

    assert logs("events") == []


def test_the_request_that_starts_a_chat_is_timed_under_that_chat(client, logs):
    started = client.post("/api/buy/init", json={"product_type": SCRIPT_PRODUCT}).get_json()

    [request] = [s for s in logs("timings") if s["name"] == "request"]
    assert request["session_id"] == started["session_id"]
