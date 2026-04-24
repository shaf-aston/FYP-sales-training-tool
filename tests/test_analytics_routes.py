import json
from pathlib import Path

from flask import Flask

from backend.routes import analytics as analytics_routes


class _DummyFlowEngine:
    def __init__(self):
        self.current_stage = "logical"
        self.flow_type = "consultative"
        self.conversation_history = [
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "I need something reliable"},
        ]


class _DummyBot:
    def __init__(self):
        self.flow_engine = _DummyFlowEngine()


def _make_analytics_app(monkeypatch, testing=True):
    app = Flask(__name__)
    app.config["TESTING"] = testing

    def require_session():
        return _DummyBot(), None

    def bot_state(_bot):
        return {"stage": "LOGICAL", "strategy": "CONSULTATIVE"}

    monkeypatch.setattr(analytics_routes.bp, "app", app, raising=False)
    monkeypatch.setattr(analytics_routes.bp, "require_session", require_session, raising=False)
    monkeypatch.setattr(analytics_routes.bp, "bot_state", bot_state, raising=False)
    app.register_blueprint(analytics_routes.bp)
    return app


def test_test_question_returns_question_and_bot_state(monkeypatch):
    app = _make_analytics_app(monkeypatch)
    monkeypatch.setattr("core.quiz.get_quiz_question", lambda quiz_type: {"prompt": quiz_type})

    response = app.test_client().get("/api/test/question?type=next-move")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "question": {"prompt": "next-move"},
        "type": "next-move",
        "stage": "LOGICAL",
        "strategy": "CONSULTATIVE",
    }


def test_test_stage_rejects_missing_answer(monkeypatch):
    app = _make_analytics_app(monkeypatch)

    response = app.test_client().post("/api/test/stage", json={"answer": " "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Answer required"


def test_next_move_uses_last_user_message(monkeypatch):
    app = _make_analytics_app(monkeypatch)
    captured = {}

    def _fake_next_move(response, bot, last_user_msg):
        captured["response"] = response
        captured["last_user_msg"] = last_user_msg
        return {"score": 9}

    monkeypatch.setattr("core.quiz.test_quiz_next_move", _fake_next_move)

    response = app.test_client().post("/api/test/next-move", json={"response": "Ask about impact"})

    assert response.status_code == 200
    assert response.get_json()["score"] == 9
    assert captured == {"response": "Ask about impact", "last_user_msg": "I need something reliable"}


def test_knowledge_route_rejects_unknown_fields(monkeypatch):
    app = _make_analytics_app(monkeypatch)

    response = app.test_client().post("/api/knowledge", json={"bad_field": "x"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Unknown fields: bad_field"


def test_knowledge_get_is_public(monkeypatch):
    app = _make_analytics_app(monkeypatch)
    monkeypatch.setattr(
        analytics_routes,
        "load_custom_knowledge",
        lambda: {"product_name": "Acme Pro"},
    )

    response = app.test_client().get("/api/knowledge")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"product_name": "Acme Pro"},
    }


def test_session_analytics_forbids_header_path_mismatch(monkeypatch):
    app = _make_analytics_app(monkeypatch)
    monkeypatch.setattr(
        analytics_routes.SessionAnalytics,
        "get_session_analytics",
        staticmethod(lambda _session_id: [{"type": "ignored"}]),
    )

    response = app.test_client().get(
        "/api/analytics/session/aaaaaaaa",
        headers={"X-Session-ID": "bbbbbbbb"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden"


def test_feedback_route_trims_comment_and_appends_jsonl(monkeypatch):
    app = _make_analytics_app(monkeypatch)
    feedback_dir = Path.cwd() / ".tmp" / "test-feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    feedback_file = feedback_dir / "feedback.jsonl"
    if feedback_file.exists():
        feedback_file.unlink()
    monkeypatch.setattr(analytics_routes, "_FEEDBACK_FILE", str(feedback_file))

    response = app.test_client().post(
        "/api/feedback",
        json={"rating": 5, "comment": "x" * 600, "page": "knowledge"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}

    lines = feedback_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["rating"] == 5
    assert entry["page"] == "knowledge"
    assert len(entry["comment"]) == 500


def test_feedback_file_stays_within_repo_root():
    repo_root = Path(__file__).resolve().parent.parent
    assert Path(analytics_routes._FEEDBACK_FILE).resolve() == repo_root / "feedback.jsonl"


def test_analytics_summary_requires_admin_token_when_not_testing(monkeypatch):
    app = _make_analytics_app(monkeypatch, testing=False)
    app.config["ADMIN_TOKEN"] = "secret-token"

    response = app.test_client().get("/api/analytics/summary")

    assert response.status_code == 403
    assert response.get_json()["error"] == "Admin token required"
