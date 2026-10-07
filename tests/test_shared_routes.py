"""Tests for the routes both modes share: knowledge, analytics and feedback."""
import logging
from pathlib import Path

from flask import Flask

import core.knowledge as knowledge_module
from backend.routes import knowledge as knowledge_routes
from backend.routes import monitoring as monitoring_routes


def _make_shared_app(testing=True):
    app = Flask(__name__)
    app.config["TESTING"] = testing
    app.register_blueprint(knowledge_routes.bp)
    app.register_blueprint(monitoring_routes.bp)
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


def test_session_analytics_forbids_header_path_mismatch(monkeypatch):
    app = _make_shared_app()
    monkeypatch.setattr(
        monitoring_routes.SessionAnalytics,
        "get_session_analytics",
        staticmethod(lambda _session_id: [{"type": "ignored"}]),
    )

    response = app.test_client().get(
        "/api/analytics/session/aaaaaaaa",
        headers={"X-Session-ID": "bbbbbbbb"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Forbidden"


def test_feedback_route_logs_without_persisting(monkeypatch, caplog):
    app = _make_shared_app()
    caplog.set_level(logging.INFO)

    response = app.test_client().post(
        "/api/feedback",
        json={"rating": 5, "comment": "x" * 600, "page": "knowledge"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert any("feedback_event" in record.message for record in caplog.records)
    assert any("x" * 500 in record.message for record in caplog.records)


def test_analytics_summary_is_public(monkeypatch):
    app = _make_shared_app(testing=False)

    response = app.test_client().get("/api/analytics/summary")

    assert response.status_code == 200
    assert response.get_json()["success"] is True
