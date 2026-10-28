"""Tests for the routes both modes share: knowledge, analytics and feedback."""
from pathlib import Path

from flask import Flask

import core.sell_mode.knowledge as knowledge_module
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


def test_knowledge_route_rejects_unknown_fields(monkeypatch):
    app = _make_shared_app()

    response = app.test_client().post("/api/knowledge", json={"bad_field": "x"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Unknown fields: bad_field"


def test_knowledge_get_is_public(monkeypatch):
    app = _make_shared_app()
    monkeypatch.setattr(
        knowledge_routes,
        "load_custom_knowledge",
        lambda: {"product_name": "Acme Pro"},
    )

    response = app.test_client().get("/api/knowledge")

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "data": {"product_name": "Acme Pro"},
    }


def test_knowledge_post_saves_to_yaml_file(monkeypatch):
    app = _make_shared_app()
    knowledge_dir = Path.cwd() / ".tmp" / "test-knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    knowledge_file = knowledge_dir / "custom_instructions.yaml"
    knowledge_file.unlink(missing_ok=True)

    monkeypatch.setattr(knowledge_module, "KNOWLEDGE_FILE", knowledge_file)

    response = app.test_client().post(
        "/api/knowledge",
        json={"product_name": "Acme Pro", "additional_notes": "Fast setup"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert knowledge_file.exists()
    assert "Acme Pro" in knowledge_file.read_text(encoding="utf-8")


def test_knowledge_delete_clears_yaml_file(monkeypatch):
    app = _make_shared_app()
    knowledge_dir = Path.cwd() / ".tmp" / "test-knowledge-clear"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    knowledge_file = knowledge_dir / "custom_instructions.yaml"
    knowledge_file.write_text("product_name: Acme Pro\n", encoding="utf-8")

    monkeypatch.setattr(knowledge_module, "KNOWLEDGE_FILE", knowledge_file)

    response = app.test_client().delete("/api/knowledge")

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert not knowledge_file.exists()


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
