"""Tests for security using STRIDE threat modeling methodology."""
from flask import Flask, jsonify, request

from backend.routes import session as session_routes
from backend.security import (
    ClientIPExtractor,
    InputValidator,
    RateLimiter,
    SecurityConfig,
    SecurityHeadersMiddleware,
)


class _DummyFlowEngine:
    def __init__(self):
        self.flow_type = "intent"
        self.initial_flow_type = "intent"
        self.current_stage = "intent"
        self.conversation_history = []

    def switch_strategy(self, strategy):
        self.flow_type = strategy
        return True


class _DummyBot:
    def __init__(self, provider_type=None, product_type=None, session_id=None):
        self.provider_type = provider_type
        self.product_type = product_type
        self.session_id = session_id
        self.flow_engine = _DummyFlowEngine()

    @staticmethod
    def load_session(_session_id):
        return None

    def save_session(self):
        pass


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


def _make_session_app(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["ADMIN_TOKEN"] = "secret-token"
    manager = _DummySessionManager()

    monkeypatch.setattr(session_routes, "SalesChatbot", _DummyBot)
    monkeypatch.setattr(
        session_routes,
        "generate_init_greeting",
        lambda _strategy: {"message": "hello", "training": {"ok": True}},
    )

    def bot_state(bot):
        return {
            "stage": "----"
            if bot.flow_engine.flow_type == "intent"
            else bot.flow_engine.current_stage.upper(),
            "strategy": bot.flow_engine.flow_type.upper(),
        }

    session_routes.init_routes(
        app,
        manager,
        manager.get,
        manager.set,
        manager.delete,
        bot_state,
    )
    app.register_blueprint(session_routes.bp)
    return app


def test_client_ip_extractor_ignores_forwarded_headers_by_default():
    app = Flask(__name__)

    with app.test_request_context(
        "/",
        headers={"X-Forwarded-For": "203.0.113.9"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert ClientIPExtractor.get_ip(request) == "127.0.0.1"


def test_client_ip_extractor_can_trust_forwarded_headers_when_enabled():
    app = Flask(__name__)
    app.config["TRUST_PROXY_HEADERS"] = True

    with app.test_request_context(
        "/",
        headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.5"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    ):
        assert ClientIPExtractor.get_ip(request) == "203.0.113.9"


def test_security_headers_add_no_store_for_api_routes():
    app = Flask(__name__)
    app.after_request(SecurityHeadersMiddleware.apply)

    @app.route("/api/ping")
    def ping():
        return jsonify({"ok": True})

    response = app.test_client().get("/api/ping")

    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_security_headers_use_the_baseline_csp_by_default():
    app = Flask(__name__)
    app.after_request(SecurityHeadersMiddleware.apply)

    @app.route("/api/ping")
    def ping():
        return jsonify({"ok": True})

    response = app.test_client().get("/api/ping")
    csp = response.headers["Content-Security-Policy"]

    assert "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp
    assert "https://js.puter.com" in csp
    assert "frame-ancestors 'none'" in csp


def test_force_strategy_override_requires_admin_token(monkeypatch):
    app = _make_session_app(monkeypatch)
    client = app.test_client()

    unauthorized = client.post("/api/init", json={"force_strategy": "transactional"})
    authorized = client.post(
        "/api/init",
        json={"force_strategy": "transactional"},
        headers={"X-Admin-Token": "secret-token"},
    )

    assert unauthorized.status_code == 200
    assert unauthorized.get_json()["strategy"] == "INTENT"

    assert authorized.status_code == 200
    assert authorized.get_json()["strategy"] == "TRANSACTIONAL"


def test_session_id_validator_rejects_malformed_identifiers():
    app = Flask(__name__)

    with app.app_context():
        error = InputValidator.validate_session_id("../bad-id")

    assert error is not None
    response, status_code = error
    assert status_code == 400
    assert response.get_json()["error"] == "Invalid session ID format"


def test_rate_limiter_retains_requests_until_window_expires():
    limiter = RateLimiter({"chat": (2, 60)})

    assert limiter.is_limited("1.2.3.4", "chat") is False
    assert limiter.is_limited("1.2.3.4", "chat") is False
    assert limiter.is_limited("1.2.3.4", "chat") is True
