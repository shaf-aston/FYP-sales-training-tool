"""Tests for prospect session recovery and persistence."""
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


class _RecoveredProspectSession:
    def __init__(self):
        self.state = type("State", (), {"has_committed": False, "has_walked": False})()

    def get_evaluation(self):
        return {"overall_score": 88, "grade": "B", "outcome": "sold"}


class _RecoveredProspectState:
    difficulty = "medium"
    product_type = "default"

    def to_dict(self):
        return {
            "readiness": 0.42,
            "objections_raised": 1,
            "turn_count": 2,
            "needs_disclosed": [],
            "has_committed": False,
            "has_walked": False,
            "difficulty": self.difficulty,
            "product_type": self.product_type,
            "persona_name": "Alex",
        }


class _RecoveredProspectStateSession:
    def __init__(self):
        self.state = _RecoveredProspectState()
        self.persona = {"name": "Alex", "background": "Professional considering a purchase"}
        self.provider_name = "stub"
        self.model_name = "stub-model"
        self.conversation_history = [
            {"role": "assistant", "content": "Hi, I'm Alex. I'm looking into options today."}
        ]


def test_prospect_evaluate_recovers_persisted_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyProspectSessionManager()

    prospect_routes.init_routes(
        app,
        manager,
        lambda message: (message, None),
    )
    app.register_blueprint(prospect_routes.bp)

    recovered = _RecoveredProspectSession()
    monkeypatch.setattr(
        "core.prospect_session.ProspectSession.load_session",
        classmethod(lambda cls, session_id: recovered if session_id == "a" * 32 else None),
    )

    response = app.test_client().post(
        "/api/prospect/evaluate",
        headers={"X-Session-ID": "a" * 32},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
    assert manager.get("a" * 32) is recovered


def test_prospect_state_recovers_persisted_session(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    manager = _DummyProspectSessionManager()

    prospect_routes.init_routes(
        app,
        manager,
        lambda message: (message, None),
    )
    app.register_blueprint(prospect_routes.bp)

    recovered = _RecoveredProspectStateSession()
    monkeypatch.setattr(
        "core.prospect_session.ProspectSession.load_session",
        classmethod(lambda cls, session_id: recovered if session_id == "b" * 32 else None),
    )

    response = app.test_client().get(
        "/api/prospect/state",
        headers={"X-Session-ID": "b" * 32},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["persona"]["name"] == "Alex"
    assert payload["conversation_history"] == recovered.conversation_history
    assert manager.get("b" * 32) is recovered
