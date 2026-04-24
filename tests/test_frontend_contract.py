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
