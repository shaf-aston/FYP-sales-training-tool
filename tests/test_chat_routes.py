"""Tests for chat API routes."""
from flask import Flask

from backend.routes import chat as chat_routes


class _DummyFlowEngine:
    def __init__(self):
        self.conversation_history = [
            {"role": "assistant", "content": "Old answer"},
            {"role": "user", "content": "Old question"},
        ]


class _DummyResponse:
    def __init__(self, content="Reply", latency_ms=12.34, provider="probe", model="probe-model"):
        self.content = content
        self.latency_ms = latency_ms
        self.provider = provider
        self.model = model
        self.input_len = 2
        self.output_len = len(content)


class _DummyBot:
    def __init__(self):
        self.flow_engine = _DummyFlowEngine()
        self.rewind_calls = []
        self.training_calls = []
        self.training_question_calls = []

    def chat(self, message):
        self.flow_engine.conversation_history.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": f"reply:{message}"},
            ]
        )
        return _DummyResponse(content=f"reply:{message}")

    def generate_training(self, user_message, bot_reply):
        self.training_calls.append((user_message, bot_reply))
        return {"what_happened": "ok"}

    def rewind_to_turn(self, turn_index):
        self.rewind_calls.append(turn_index)
        self.flow_engine.conversation_history = []
        return True

    def get_conversation_summary(self):
        return {"turns": len(self.flow_engine.conversation_history) // 2}

    def answer_training_question(self, question, style="tactical"):
        self.training_question_calls.append((question, style))
        return {"answer": f"{style}:{question}"}


def _make_chat_app(monkeypatch, bot=None):
    app = Flask(__name__)
    app.config["TESTING"] = True
    bot = bot or _DummyBot()

    def require_session():
        return bot, None

    def validate_message(text):
        text = (text or "").strip()
        if not text:
            from flask import jsonify

            return None, (jsonify({"error": "Message required"}), 400)
        return text, None

    def bot_state(_bot):
        return {"stage": "INTENT", "strategy": "CONSULTATIVE"}

    monkeypatch.setattr(chat_routes.bp, "app", app, raising=False)
    monkeypatch.setattr(chat_routes.bp, "require_session", require_session, raising=False)
    monkeypatch.setattr(chat_routes.bp, "validate_message", validate_message, raising=False)
    monkeypatch.setattr(chat_routes.bp, "bot_state", bot_state, raising=False)
    app.register_blueprint(chat_routes.bp)
    return app, bot


def test_chat_route_returns_metrics_and_training_blob(monkeypatch):
    app, bot = _make_chat_app(monkeypatch)

    response = app.test_client().post("/api/chat", json={"message": "Hi"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["message"] == "reply:Hi"
    assert payload["metrics"] == {"input_length": 2, "output_length": len("reply:Hi")}
    assert payload["training"] == {"what_happened": "ok"}
    assert bot.training_calls == [("Hi", "reply:Hi")]


def test_chat_route_handles_missing_json_body(monkeypatch):
    app, _bot = _make_chat_app(monkeypatch)

    response = app.test_client().post(
        "/api/chat",
        data="",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Message required"


def test_edit_route_rewinds_before_regenerating_response(monkeypatch):
    app, bot = _make_chat_app(monkeypatch)

    response = app.test_client().post("/api/edit", json={"index": 1, "message": "Updated"})
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert bot.rewind_calls == [0]
    assert payload["message"] == "reply:Updated"
    assert payload["history"] == [
        {"role": "user", "content": "Updated"},
        {"role": "assistant", "content": "reply:Updated"},
    ]


def test_edit_route_rejects_invalid_index_format(monkeypatch):
    app, _bot = _make_chat_app(monkeypatch)

    response = app.test_client().post("/api/edit", json={"index": "abc", "message": "Updated"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid index format"


def test_summary_route_returns_bot_summary(monkeypatch):
    app, _bot = _make_chat_app(monkeypatch)

    response = app.test_client().get("/api/summary")

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "summary": {"turns": 1}}


def test_training_ask_defaults_unknown_style_to_tactical(monkeypatch):
    app, bot = _make_chat_app(monkeypatch)

    response = app.test_client().post(
        "/api/training/ask",
        json={"question": "What should I ask next?", "style": "invalid"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {"success": True, "answer": "tactical:What should I ask next?"}
    assert bot.training_question_calls == [("What should I ask next?", "tactical")]


def test_training_ask_rejects_missing_question(monkeypatch):
    app, _bot = _make_chat_app(monkeypatch)

    response = app.test_client().post("/api/training/ask", json={"question": "  "})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Question required"
