"""Removed features stay removed: their routes, files and names do not come back."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("old", ["/api/init", "/api/chat", "/api/test/question", "/api/prospect/init"])
def test_old_paths_are_gone(client, old):
    # Nothing answers: 404, or 405 from the page catch-all, which only takes GET.
    assert client.post(old, json={}).status_code in (404, 405)


def test_removed_buy_endpoints_are_gone(live_seller):
    """Restore and the old strategy/stage switches no longer exist: the script owns the call."""
    client, _seller, headers = live_seller

    responses = [
        client.post("/api/buy/restore", json={"history": [{"role": "user", "content": "Hi"}]}),
        client.post("/api/buy/strategy", headers=headers, json={"strategy": "transactional"}),
        client.post("/api/buy/stage", headers=headers, json={"stage": "pitch"}),
        client.get("/api/buy/stages", headers=headers),
        client.get("/api/buy/config"),
    ]

    assert [r.status_code for r in responses] == [404] * 5


def test_debug_panel_references_removed_from_runtime_files():
    files = [
        ROOT / "backend" / "app.py",
        *sorted(p for p in (ROOT / "web" / "src").rglob("*") if p.suffix in {".ts", ".tsx", ".css"}),
    ]
    forbidden = ["debug_enabled", "PAGE_DEBUG", "devPanel", "toggleDevPanel", "/api/debug", "devToggleBtn"]

    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for token in forbidden:
        assert token not in combined


def test_web_search_references_removed_from_core_runtime_files():
    files = [ROOT / "core" / "seller_bot.py", ROOT / "core" / "constants.py", ROOT / "core" / "loader.py"]
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


def test_the_dead_needs_list_is_gone():
    """Nothing read it, so it was removed rather than given a made-up meaning."""
    from core.buyer_state import BuyerState

    assert "needs_disclosed" not in BuyerState(readiness=0.5, difficulty="easy").to_dict()
