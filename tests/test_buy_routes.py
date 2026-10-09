"""Buy-mode routes (/api/buy): session start and end, chat, edit, coach, and the shared health check."""
import pytest

from backend.routes import monitoring as monitoring_routes


def test_chat_route_returns_metrics_and_coach_notes(live_seller):
    client, _seller, headers = live_seller

    response = client.post("/api/buy/chat", json={"message": "Hi"}, headers=headers)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] == "reply:Hi"
    assert payload["metrics"] == {"input_length": 2, "output_length": len("reply:Hi")}
    assert payload["training"] == {"what_happened": "ok"}
    assert (payload["stage"], payload["strategy"]) == ("INTENT", "CONSULTATIVE")


def test_chat_route_handles_missing_json_body(live_seller):
    client, _seller, headers = live_seller

    response = client.post("/api/buy/chat", data="", content_type="text/plain", headers=headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Message required"


def test_edit_route_replays_from_the_edited_message(live_seller):
    client, seller, headers = live_seller
    seller.call.conversation_history = [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "Old question"},
        {"role": "assistant", "content": "Old answer"},
    ]

    response = client.post("/api/buy/edit", json={"index": 1, "message": "Updated"}, headers=headers)
    payload = response.get_json()

    assert response.status_code == 200
    assert seller.edits == [1]
    assert payload["message"] == "reply:Updated"
    assert payload["history"] == [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "Updated"},
        {"role": "assistant", "content": "reply:Updated"},
    ]


def test_edit_route_rejects_invalid_index_format(live_seller):
    client, _seller, headers = live_seller

    response = client.post("/api/buy/edit", json={"index": "abc", "message": "Updated"}, headers=headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid index format"


def test_coach_defaults_unknown_style_to_tactical(live_seller):
    client, seller, headers = live_seller

    response = client.post(
        "/api/buy/coach", json={"question": "What should I ask next?", "style": "invalid"}, headers=headers
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "answer": "tactical:What should I ask next?"}
    assert seller.coach_questions == [("What should I ask next?", "tactical")]


def test_coach_rejects_missing_question(live_seller):
    client, _seller, headers = live_seller

    response = client.post("/api/buy/coach", json={"question": "  "}, headers=headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Question required"


def test_health_returns_active_provider_and_performance(live_seller, monkeypatch):
    client, _seller, headers = live_seller
    monkeypatch.setattr(
        monitoring_routes, "get_available_providers",
        lambda: [{"name": "probe", "available": True, "model": "probe-model"}]
    )
    monkeypatch.setattr(
        monitoring_routes.PerformanceTracker,
        "get_provider_stats",
        staticmethod(lambda: {"probe": {"count": 1}}),
    )

    response = client.get("/api/health", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "active": {"provider": "probe", "model": "probe-model"},
        "available_providers": [{"name": "probe", "available": True, "model": "probe-model"}],
        "performance_stats": {"probe": {"count": 1}},
    }


def test_reset_route_deletes_the_session_and_records_its_end(live_seller, buy_app):
    client, seller, headers = live_seller

    response = client.post("/api/buy/reset", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert seller.session_ended
    assert buy_app.extensions["sessions"].seller.get(seller.session_id) is None


def test_init_creates_new_session_and_returns_greeting(buy_app):
    response = buy_app.test_client().post("/api/buy/init", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["message"] == "hello"
    assert payload["history"] == []
    # The greeting is kept in the call so the seller never greets twice.
    seller = buy_app.extensions["sessions"].seller.get(payload["session_id"])
    assert seller.call.conversation_history == [{"role": "assistant", "content": "hello"}]


def test_init_restores_live_session_from_memory(live_seller):
    client, seller, _headers = live_seller
    seller.call.conversation_history = [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Great"},
    ]

    payload = client.post("/api/buy/init", json={"session_id": seller.session_id}).get_json()

    assert payload["success"] is True
    assert payload["message"] is None
    assert len(payload["history"]) == 3


def test_init_starts_fresh_session_when_missing_from_memory(buy_app):
    payload = buy_app.test_client().post("/api/buy/init", json={"session_id": "disk0001"}).get_json()

    assert payload["success"] is True
    assert payload["message"] == "hello"
    assert payload["session_id"] != "disk0001"
    assert buy_app.extensions["sessions"].seller.get(payload["session_id"]) is not None


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/api/buy/reset"),
        ("post", "/api/buy/chat"),
        ("post", "/api/buy/edit"),
        ("post", "/api/buy/coach"),
        ("get", "/api/buy/quiz/question"),
        ("post", "/api/buy/quiz/stage"),
        ("post", "/api/buy/quiz/next-move"),
        ("post", "/api/buy/quiz/direction"),
    ],
)
def test_every_session_route_answers_a_dead_session_the_same_way(buy_app, method, path):
    """One seam, one contract: the web app starts over on code == SESSION_EXPIRED."""
    client = buy_app.test_client()
    kwargs = {"headers": {"X-Session-ID": "f" * 8}}
    if method == "post":
        kwargs["json"] = {"message": "Hi", "index": 1, "question": "Why?", "answer": "x"}

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_EXPIRED"
