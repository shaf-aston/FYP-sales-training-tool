"""Request security: client IP, headers, session ids, rate limits and the session store."""
from flask import Flask, jsonify, request

from backend.security import (
    ClientIPExtractor,
    InputValidator,
    RateLimiter,
    SecurityHeadersMiddleware,
    SessionStore,
)


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


def test_session_id_validator_rejects_malformed_identifiers():
    app = Flask(__name__)

    with app.app_context():
        error = InputValidator.validate_session_id("../bad-id")

    assert error is not None
    response, status_code = error
    assert status_code == 400
    assert response.get_json()["error"] == "Invalid session ID format"


def test_rate_limiter_retains_requests_until_window_expires():
    limiter = RateLimiter({"buy_chat": (2, 60)})

    assert limiter.is_limited("1.2.3.4", "buy_chat") is False
    assert limiter.is_limited("1.2.3.4", "buy_chat") is False
    assert limiter.is_limited("1.2.3.4", "buy_chat") is True


def test_background_cleanup_is_idempotent(monkeypatch):
    started = []

    class DummyThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.daemon))

    monkeypatch.setattr("backend.security.threading.Thread", DummyThread)

    store = SessionStore(max_sessions=1, idle_minutes=1, cleanup_interval=60, name="test sessions")
    store.start_background_cleanup()
    store.start_background_cleanup()

    assert len(started) == 1
