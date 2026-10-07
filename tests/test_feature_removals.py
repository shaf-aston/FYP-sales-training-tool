"""Tests for removed features and dead code verification."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_debug_panel_references_removed_from_runtime_files():
    files = [
        ROOT / "backend" / "app.py",
        *sorted(p for p in (ROOT / "web" / "src").rglob("*") if p.suffix in {".ts", ".tsx", ".css"}),
    ]
    forbidden = [
        "debug_enabled",
        "PAGE_DEBUG",
        "devPanel",
        "toggleDevPanel",
        "/api/debug",
        "devToggleBtn",
    ]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for token in forbidden:
        assert token not in combined


def test_web_search_references_removed_from_core_runtime_files():
    files = [
        ROOT / "core" / "seller_bot.py",
        ROOT / "core" / "constants.py",
        ROOT / "core" / "loader.py",
    ]
    forbidden = [
        "load_web_search_config",
        "should_trigger_web_search",
        "build_search_query",
        "WebSearchService",
        "record_web_search",
        "MAX_SEARCH_RESULTS",
        "MIN_SECONDS_BETWEEN_SEARCHES",
        "SEARCH_CACHE_TTL_SECONDS",
    ]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for token in forbidden:
        assert token not in combined


def test_deleted_feature_files_are_absent():
    assert not (ROOT / "backend" / "routes" / "debug.py").exists()
    assert not (ROOT / "core" / "web_search.py").exists()
