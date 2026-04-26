"""Tests for prospect session lifecycle without replay recovery."""
from flask import Flask

from backend.routes import prospect as prospect_routes


class _DummyProspectSessionManager:
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


def test_prospect_evaluate_requires_in_memory_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyProspectSessionManager()
    load_calls = {"count": 0}

    prospect_routes.init_routes(
        app,
        manager,
        lambda message: (message, None),
    )
    app.register_blueprint(prospect_routes.bp)

    monkeypatch.setattr(
        "core.prospect_session.ProspectSession.load_session",
        classmethod(
            lambda cls, session_id: load_calls.__setitem__("count", load_calls["count"] + 1)
            or None
        ),
    )

    response = app.test_client().post(
        "/api/prospect/evaluate",
        headers={"X-Session-ID": "a" * 32},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_EXPIRED"
    assert load_calls["count"] == 0


def test_prospect_state_requires_in_memory_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyProspectSessionManager()
    load_calls = {"count": 0}

    prospect_routes.init_routes(
        app,
        manager,
        lambda message: (message, None),
    )
    app.register_blueprint(prospect_routes.bp)

    monkeypatch.setattr(
        "core.prospect_session.ProspectSession.load_session",
        classmethod(
            lambda cls, session_id: load_calls.__setitem__("count", load_calls["count"] + 1)
            or None
        ),
    )

    response = app.test_client().get(
        "/api/prospect/state",
        headers={"X-Session-ID": "b" * 32},
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_EXPIRED"
    assert load_calls["count"] == 0
