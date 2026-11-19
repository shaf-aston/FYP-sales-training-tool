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


def _ip(headers, trust=True):
    app = Flask(__name__)
    app.config["TRUST_PROXY_HEADERS"] = trust
    with app.test_request_context("/", headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}):
        return ClientIPExtractor.get_ip(request), ClientIPExtractor.peer(request)


def test_trusted_peer_is_the_address_caddy_saw_not_what_the_caller_wrote():
    # Caddy writes the connecting address last; anything before it came from the caller
    assert _ip({"X-Forwarded-For": "6.6.6.6, 203.0.113.9"}) == ("203.0.113.9", "203.0.113.9")


def test_visitor_behind_vercel_comes_from_x_real_ip():
    assert _ip({"X-Forwarded-For": "76.76.21.21", "X-Real-IP": "198.51.100.7"}) == ("198.51.100.7", "76.76.21.21")


def test_junk_headers_fall_back_to_what_can_be_trusted():
    assert _ip({"X-Forwarded-For": "76.76.21.21", "X-Real-IP": "not-an-ip"}) == ("76.76.21.21", "76.76.21.21")
    assert _ip({"X-Forwarded-For": "garbage", "X-Real-IP": ""}) == ("127.0.0.1", "127.0.0.1")
    assert _ip({}) == ("127.0.0.1", "127.0.0.1")


def test_untrusted_ignores_every_proxy_header():
    assert _ip({"X-Forwarded-For": "203.0.113.9", "X-Real-IP": "198.51.100.7"}, trust=False) == ("127.0.0.1", "127.0.0.1")


def _limited_app(monkeypatch, limits):
    from backend import security

    monkeypatch.setattr(security, "_rate_limiter", RateLimiter(limits))
    monkeypatch.setattr(security, "RATE_LIMIT_PEER_FACTOR", 3)
    app = Flask(__name__)
    app.config["TRUST_PROXY_HEADERS"] = True

    @app.route("/hit")
    @security.require_rate_limit("b")
    def hit():
        return "ok"

    return app.test_client()


def test_two_visitors_get_separate_buckets(monkeypatch):
    client = _limited_app(monkeypatch, {"b": (2, 60)})
    a = {"X-Forwarded-For": "76.76.21.21", "X-Real-IP": "198.51.100.1"}
    b = {"X-Forwarded-For": "76.76.21.21", "X-Real-IP": "198.51.100.2"}
    assert [client.get("/hit", headers=a).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/hit", headers=b).status_code == 200
    assert client.get("/hit", headers={"X-Forwarded-For": "203.0.113.5"}).status_code == 200   # a direct caller


def test_a_caller_naming_many_visitors_still_hits_the_peer_limit(monkeypatch):
    client = _limited_app(monkeypatch, {"b": (2, 60)})
    codes = [client.get("/hit", headers={"X-Forwarded-For": "203.0.113.5", "X-Real-IP": f"198.51.100.{i}"}).status_code
             for i in range(8)]
    assert codes == [200] * 6 + [429] * 2   # 2 x factor 3 for the one connecting address


def test_limiter_forgets_callers_whose_window_emptied(monkeypatch):
    from backend import security

    limiter = RateLimiter({"b": (5, 60)})
    now = [1000.0]
    monkeypatch.setattr(security.time, "time", lambda: now[0])
    for i in range(limiter.SWEEP_EVERY - 1):
        limiter.is_limited(f"10.0.{i // 250}.{i % 250}", "b")
    now[0] += 120
    limiter.is_limited("10.9.9.9", "b")   # the sweep runs on this call
    assert list(limiter._store) == ["b:10.9.9.9"]


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
