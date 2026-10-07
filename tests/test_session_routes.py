"""Tests for session management API routes."""
from flask import Flask

from backend.routes import session as session_routes
from backend.routes._utils import Sessions


class _DummyFlowEngine:
    def __init__(self):
        self.flow_type = "consultative"
        self.current_stage = "intent"
        self.conversation_history = []


class _DummyBot:
    loaded_session_id = None

    def __init__(self, provider_type=None, product_type=None, session_id=None):
        self.provider_type = provider_type
        self.product_type = product_type
        self.session_id = session_id
        self.provider_name = provider_type or "probe"
        self.model_name = "probe-model"
        self.flow_engine = _DummyFlowEngine()
        self.saved = False
        self.session_ended = False

    def record_session_end(self):
        self.session_ended = True

    def save_session(self):
        self.saved = True

    def script_opening(self):
        return "hello"

    def open_with(self, greeting):
        self.flow_engine.conversation_history.append({"role": "assistant", "content": greeting})

    def generate_training(self, user_msg, bot_reply):
        return {"tip": "x"}

    @staticmethod
    def load_session(session_id):
        _DummyBot.loaded_session_id = session_id
        return None


class _DummySessionManager:
    def __init__(self):
        self._sessions = {}

    def can_create(self):
        return True

    def get(self, session_id):
        return self._sessions.get(session_id)

    def set(self, session_id, bot):
        self._sessions[session_id] = bot

    def delete(self, session_id):
        self._sessions.pop(session_id, None)


def _make_session_app(monkeypatch, testing=True):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    manager = _DummySessionManager()

    monkeypatch.setattr(session_routes, "SellerBot", _DummyBot)

    app.extensions["sessions"] = Sessions(seller=manager, buyer=None)
    app.register_blueprint(session_routes.bp)
    return app, manager


def test_removed_endpoints_are_gone(monkeypatch):
    """Restore and the old strategy/stage switches no longer exist: the script owns the call."""
    app, manager = _make_session_app(monkeypatch)
    client = app.test_client()
    manager.set("a" * 8, _DummyBot(session_id="a" * 8))
    headers = {"X-Session-ID": "a" * 8}

    responses = [
        client.post("/api/restore", json={"history": [{"role": "user", "content": "Hi"}]}),
        client.post("/api/strategy", headers=headers, json={"strategy": "transactional"}),
        client.post("/api/stage", headers=headers, json={"stage": "pitch"}),
        client.get("/api/stages", headers=headers),
        client.get("/api/config"),
    ]

    assert [r.status_code for r in responses] == [404] * 5


def test_health_returns_active_provider_and_performance(monkeypatch):
    app, manager = _make_session_app(monkeypatch)
    bot = _DummyBot(session_id="abc12345")
    manager.set("abc12345", bot)

    monkeypatch.setattr(
        session_routes, "get_available_providers",
        lambda: [{"name": "probe", "available": True, "model": "probe-model"}]
    )
    monkeypatch.setattr(
        session_routes.PerformanceTracker,
        "get_provider_stats",
        staticmethod(lambda: {"probe": {"count": 1}}),
    )

    response = app.test_client().get("/api/health", headers={"X-Session-ID": "abc12345"})

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "active": {"provider": "probe", "model": "probe-model"},
        "available_providers": [{"name": "probe", "available": True, "model": "probe-model"}],
        "performance_stats": {"probe": {"count": 1}},
    }


def test_reset_route_deletes_existing_session(monkeypatch):
    app, manager = _make_session_app(monkeypatch)
    manager.set("c" * 8, _DummyBot(session_id="c" * 8))

    response = app.test_client().post("/api/reset", headers={"X-Session-ID": "c" * 8})

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert manager.get("c" * 8) is None


# --- /api/init path tests ---

def test_init_creates_new_session_and_returns_greeting(monkeypatch):
    """New session: returns greeting message and empty history."""
    app, manager = _make_session_app(monkeypatch)

    response = app.test_client().post("/api/init", json={})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] == "hello"
    assert payload["history"] == []
    assert payload["session_id"] is not None
    # Greeting must be stored in the bot so the LLM sees it as context
    sid = payload["session_id"]
    bot = manager.get(sid)
    assert any(
        m["role"] == "assistant" and m["content"] == "hello"
        for m in bot.flow_engine.conversation_history
    )


def test_init_restores_live_session_from_memory(monkeypatch):
    """Existing session in memory: returns full history, no new greeting."""
    app, manager = _make_session_app(monkeypatch)

    bot = _DummyBot(session_id="live0001")
    bot.flow_engine.conversation_history = [
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Great"},
    ]
    manager.set("live0001", bot)

    response = app.test_client().post("/api/init", json={"session_id": "live0001"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] is None
    assert len(payload["history"]) == 3


def test_init_starts_fresh_session_when_missing_from_memory(monkeypatch):
    """Missing in-memory sessions should start fresh instead of recovering from disk."""
    app, manager = _make_session_app(monkeypatch)

    _DummyBot.loaded_session_id = None

    response = app.test_client().post("/api/init", json={"session_id": "disk0001"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] == "hello"
    assert payload["history"] == []
    assert _DummyBot.loaded_session_id is None
    assert manager.get(payload["session_id"]) is not None


def test_every_session_route_answers_a_dead_session_the_same_way(monkeypatch):
    """One seam, one contract: the frontend recovers on code == SESSION_EXPIRED."""
    app, _manager = _make_session_app(monkeypatch)
    client = app.test_client()
    headers = {"X-Session-ID": "f" * 8}

    responses = [
        client.post("/api/reset", headers=headers),
    ]

    assert [r.status_code for r in responses] == [400]
    assert all(r.get_json()["code"] == "SESSION_EXPIRED" for r in responses)
