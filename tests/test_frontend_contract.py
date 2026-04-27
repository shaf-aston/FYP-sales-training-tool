"""Tests for frontend API contract and response format validation."""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_index_inline_handlers_exist_in_app_js():
    html = (ROOT / "frontend" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

    handlers = set(re.findall(r'onclick="\s*([A-Za-z_][A-Za-z0-9_]*)\(', html))
    defined_functions = set(
        re.findall(r"(?m)^(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", js)
    )

    missing_handlers = handlers - defined_functions

    assert not missing_handlers, (
        "Inline frontend handlers referenced by index.html must exist in app.js. "
        f"Missing: {sorted(missing_handlers)}"
    )


def test_prospect_frontend_state_is_declared():
    js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

    for required_declaration in (
        "let _prospectMode = false;",
        "let _prospectSessionId = null;",
        'let _prospectDifficulty = "medium";',
        "let _prospectSettings = {",
    ):
        assert required_declaration in js


def test_frontend_does_not_persist_transcripts_or_sessions():
    js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

    for forbidden in (
        'localStorage.setItem("chatHistory"',
        'localStorage.getItem("chatHistory"',
        'localStorage.setItem("sessionId"',
        'localStorage.getItem("sessionId"',
        'localStorage.setItem("prospectSessionId"',
        'localStorage.getItem("prospectSessionId"',
        'localStorage.setItem("chatStage"',
        'localStorage.setItem("chatStrategy"',
    ):
        assert forbidden not in js


def test_flow_controls_reuse_shared_session_recovery_path():
    js = (ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")

    assert "let _sessionRecoveryInProgress = false;" in js
    assert "function handleServerSessionError(data, { notify = true } = {})" in js
    assert "if (_sessionRecoveryInProgress) {" in js
    assert "if (handleServerSessionError(data, { notify: true })) {" in js
    assert "if (handleServerSessionError(data, { notify: false })) {" in js
