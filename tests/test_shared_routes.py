"""Tests for the routes both modes share: analytics and feedback (knowledge: test_knowledge.py)."""

from flask import Flask

from backend.request_log import RequestLog
from backend.routes import knowledge as knowledge_routes
from backend.routes import monitoring as monitoring_routes


def _make_shared_app(testing=True):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    app.register_blueprint(knowledge_routes.bp)
    app.register_blueprint(monitoring_routes.bp)
    app.wsgi_app = RequestLog(app.wsgi_app)
    return app


def test_feedback_is_kept_in_the_feedback_stream_with_its_session(logs):
    app = _make_shared_app()

    response = app.test_client().post(
        "/api/feedback",
        json={"rating": 5, "comment": "x" * 600, "page": "knowledge"},
        headers={"X-Session-ID": "feedback-session-1"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    [saved] = logs("feedback")
    assert (saved["rating"], saved["comment"], saved["page"]) == (5, "x" * 500, "knowledge")
    assert saved["session_id"] == "feedback-session-1"
