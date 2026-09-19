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


def _wire_routes(monkeypatch, app, manager):
    """Point the prospect blueprint at this test's app and manager.

    Via monkeypatch, not init_routes: the blueprint is module-global, so calling
    init_routes here would leave a permissive message validator in place for every
    test that runs afterwards in the same process.
    """
    for name, value in (
        ("app", app),
        ("prospect_session_manager", manager),
        ("validate_message", lambda message: (message, None)),
    ):
        monkeypatch.setattr(prospect_routes.bp, name, value, raising=False)


def test_prospect_evaluate_requires_in_memory_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyProspectSessionManager()
    load_calls = {"count": 0}

    _wire_routes(monkeypatch, app, manager)
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

    _wire_routes(monkeypatch, app, manager)
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
