"""Tests for the buy-mode quiz routes (/api/buy/quiz/*)."""
from flask import Flask

from backend.routes import buy as buy_routes


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

    def run_quiz_stage_answer(self, answer):
        from core.quiz import test_quiz_stage_answer
        return test_quiz_stage_answer(answer, self.flow_engine.current_stage, self.flow_engine.flow_type)

    def run_quiz_next_move(self, response):
        from core.quiz import test_quiz_next_move
        history = self.flow_engine.conversation_history
        last_user_msg = next(
            (m.get("content", "") for m in reversed(history) if m.get("role") == "user"), ""
        )
        return test_quiz_next_move(
            response, None, self.flow_engine.current_stage, self.flow_engine.flow_type, last_user_msg
        )

    def run_quiz_direction(self, explanation):
        from core.quiz import test_quiz_direction
        return test_quiz_direction(explanation, None, self.flow_engine.current_stage, self.flow_engine.flow_type)


def _make_quiz_app(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True

    def require_session():
        return _DummyBot(), None

    def bot_state(_bot):
        return {"stage": "LOGICAL", "strategy": "CONSULTATIVE"}

    monkeypatch.setattr(buy_routes, "require_session", require_session)
    monkeypatch.setattr(buy_routes, "bot_state", bot_state)
    app.register_blueprint(buy_routes.bp)
    return app


def test_quiz_question_returns_question_and_bot_state(monkeypatch):
    app = _make_quiz_app(monkeypatch)
    monkeypatch.setattr("backend.routes.buy.get_quiz_question", lambda quiz_type: {"prompt": quiz_type})

    response = app.test_client().get("/api/buy/quiz/question?type=next-move")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "question": {"prompt": "next-move"},
        "type": "next-move",
        "stage": "LOGICAL",
        "strategy": "CONSULTATIVE",
    }


def test_quiz_stage_rejects_missing_answer(monkeypatch):
    app = _make_quiz_app(monkeypatch)

    response = app.test_client().post("/api/buy/quiz/stage", json={"answer": " "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Answer required"


def test_quiz_next_move_returns_score(monkeypatch):
    captured = {}

    def _fake_run_quiz_next_move(self, response):
        captured["response"] = response
        return {"score": 9}

    monkeypatch.setattr(_DummyBot, "run_quiz_next_move", _fake_run_quiz_next_move)
    app = _make_quiz_app(monkeypatch)

    response = app.test_client().post("/api/buy/quiz/next-move", json={"response": "Ask about impact"})

    assert response.status_code == 200
    assert response.get_json()["score"] == 9
    assert captured == {"response": "Ask about impact"}
