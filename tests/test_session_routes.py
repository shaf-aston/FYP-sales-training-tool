"""Tests for session management API routes."""
from flask import Flask

from backend.routes import session as session_routes
from backend.security import SecurityConfig


class _DummyFlowEngine:
    def __init__(self):
        self.flow_type = "intent"
        self.initial_flow_type = "intent"
        self.current_stage = "intent"
        self.flow_config = {"stages": ["logical", "pitch", "outcome"]}
        self.conversation_history = []

    def advance(self, target_stage):
        self.current_stage = target_stage

    def switch_strategy(self, strategy):
        self.flow_type = strategy
        self.current_stage = "logical"
        return True


class _DummyBot:
    replayed_history = None
    loaded_session_id = None

    def __init__(self, provider_type=None, product_type=None, session_id=None):
        self.provider_type = provider_type
        self.product_type = product_type
        self.session_id = session_id
        self.provider_name = provider_type or "probe"
        self.model_name = "probe-model"
        self.flow_engine = _DummyFlowEngine()
        self.saved = False

    def replay(self, history):
        type(self).replayed_history = history

    def save_session(self):
        self.saved = True

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

    monkeypatch.setattr(session_routes, "SalesChatbot", _DummyBot)
    monkeypatch.setattr(
        session_routes,
        "generate_init_greeting",
        lambda _strategy: {"message": "hello", "training": {"tip": "x"}},
    )

    def bot_state(bot):
        return {
            "stage": "----" if bot.flow_engine.flow_type == "intent" else bot.flow_engine.current_stage.upper(),
            "strategy": bot.flow_engine.flow_type.upper(),
        }

    monkeypatch.setattr(session_routes.bp, "app", app, raising=False)
    monkeypatch.setattr(session_routes.bp, "session_manager", manager, raising=False)
    monkeypatch.setattr(session_routes.bp, "get_session", manager.get, raising=False)
    monkeypatch.setattr(session_routes.bp, "set_session", manager.set, raising=False)
    monkeypatch.setattr(session_routes.bp, "delete_session", manager.delete, raising=False)
    monkeypatch.setattr(session_routes.bp, "bot_state", bot_state, raising=False)
    app.register_blueprint(session_routes.bp)
    return app, manager


def test_restore_endpoint_is_disabled(monkeypatch):
    app, _manager = _make_session_app(monkeypatch)
    client = app.test_client()

    response = client.post(
        "/api/restore",
        json={"history": [{"role": "user", "content": "Hi"}]},
    )
    payload = response.get_json()

    assert response.status_code == 410
    assert payload["code"] == "SESSION_REPLAY_DISABLED"


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
        "ok": True,
        "active": {"provider": "probe", "model": "probe-model"},
        "available_providers": [{"name": "probe", "available": True, "model": "probe-model"}],
        "performance_stats": {"probe": {"count": 1}},
    }


def test_config_returns_limits_and_product_options(monkeypatch):
    app, _manager = _make_session_app(monkeypatch)
    monkeypatch.setattr(
        "core.loader.load_product_config",
        lambda: {
            "products": {
                "default": {"strategy": "intent", "context": "Default product"},
                "solar": {"strategy": "consultative", "context": "Solar package"},
            }
        },
    )

    response = app.test_client().get("/api/config")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["limits"]["max_message_length"] == SecurityConfig.MAX_MESSAGE_LENGTH
    assert payload["product_options"] == [
        {"id": "default", "strategy": "intent", "label": "Default product"},
        {"id": "solar", "strategy": "consultative", "label": "Solar package"},
    ]
    assert payload["features"] == {
        "flow_controls_enabled": True,
    }


def test_stage_route_mutates_current_stage(monkeypatch):
    app, manager = _make_session_app(monkeypatch)
    bot = _DummyBot(session_id="a" * 8)
    manager.set("a" * 8, bot)

    response = app.test_client().post(
        "/api/stage",
        headers={"X-Session-ID": "a" * 8},
        json={"stage": "pitch"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "stage": "----", "strategy": "INTENT"}
    assert bot.flow_engine.current_stage == "pitch"


def test_strategy_route_switches_and_persists(monkeypatch):
    app, manager = _make_session_app(monkeypatch)
    bot = _DummyBot(session_id="b" * 8)
    manager.set("b" * 8, bot)

    response = app.test_client().post(
        "/api/strategy",
        headers={"X-Session-ID": "b" * 8},
        json={"strategy": "consultative"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "stage": "LOGICAL", "strategy": "CONSULTATIVE"}
    assert bot.saved is True
    assert bot.flow_engine.initial_flow_type == "consultative"


def test_reset_route_deletes_existing_session(monkeypatch):
    app, manager = _make_session_app(monkeypatch)
    manager.set("c" * 8, _DummyBot(session_id="c" * 8))

    response = app.test_client().post("/api/reset", headers={"X-Session-ID": "c" * 8})

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert manager.get("c" * 8) is None


def test_stage_route_requires_admin_token_when_enabled(monkeypatch):
    app, manager = _make_session_app(monkeypatch, testing=False)
    app.config["REQUIRE_ADMIN_FOR_STAGE_MUTATION"] = True
    app.config["ADMIN_TOKEN"] = "secret-token"
    manager.set("d" * 8, _DummyBot(session_id="d" * 8))

    response = app.test_client().post(
        "/api/stage",
        headers={"X-Session-ID": "d" * 8},
        json={"stage": "pitch"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Admin token required"


def test_stage_route_is_open_by_default_outside_tests(monkeypatch):
    app, manager = _make_session_app(monkeypatch, testing=False)
    app.config["ADMIN_TOKEN"] = "secret-token"
    manager.set("e" * 8, _DummyBot(session_id="e" * 8))

    response = app.test_client().post(
        "/api/stage",
        headers={"X-Session-ID": "e" * 8},
        json={"stage": "pitch"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "stage": "----", "strategy": "INTENT"}


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
