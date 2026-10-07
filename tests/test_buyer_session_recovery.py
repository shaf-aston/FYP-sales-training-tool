"""Tests for sell session lifecycle without replay recovery."""
from flask import Flask

from backend.routes import sell as sell_routes
from backend.routes._utils import Sessions


class _DummyBuyerSessionManager:
    def __init__(self):
        self._sessions = {}

    def get(self, session_id):
        return self._sessions.get(session_id)

    def set(self, session_id, session):
        self._sessions[session_id] = session

    def delete(self, session_id):
        self._sessions.pop(session_id, None)

    def can_create(self):
        return True


def _wire_routes(monkeypatch, app, manager):
    """Give this test's app its own buyer registry and a permissive message validator."""
    app.extensions["sessions"] = Sessions(seller=None, buyer=manager)
    monkeypatch.setattr(sell_routes, "validate_message", lambda message: (message, None))


def test_sell_evaluate_requires_in_memory_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyBuyerSessionManager()

    _wire_routes(monkeypatch, app, manager)
    app.register_blueprint(sell_routes.bp)

    response = app.test_client().post(
        "/api/sell/evaluate",
        headers={"X-Session-ID": "a" * 32},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_EXPIRED"


def test_sell_state_requires_in_memory_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyBuyerSessionManager()

    _wire_routes(monkeypatch, app, manager)
    app.register_blueprint(sell_routes.bp)

    response = app.test_client().get(
        "/api/sell/state",
        headers={"X-Session-ID": "b" * 32},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_EXPIRED"
