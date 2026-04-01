"""Unit tests for web search enrichment.

All tests mock duckduckgo_search at the module level — no network calls.
"""

import time

from chatbot.web_search import WebSearchService, SearchResult, SearchResponse
from chatbot.analysis import should_trigger_web_search, build_search_query


# ---------------------------------------------------------------------------
# WebSearchService tests
# ---------------------------------------------------------------------------

class TestWebSearchService:

    def _make_service(self) -> WebSearchService:
        return WebSearchService(cache_ttl=1800)

    def test_graceful_failure_on_network_error(self, monkeypatch):
        """search() must return SearchResponse(error=...) and never raise."""
        def bad_fetch(*args, **kwargs):
            raise ConnectionError("no network")

        svc = self._make_service()
        monkeypatch.setattr(svc, "_fetch", bad_fetch)

        response = svc.search("ROI statistics cars cost savings")

        assert isinstance(response, SearchResponse)
        assert response.error is not None
        assert response.results == []

    def test_cache_hit_skips_network_call(self, monkeypatch):
        """Second call with same query within TTL must not invoke _fetch again."""
        call_count = {"n": 0}

        def counting_fetch(query, max_results):
            call_count["n"] += 1
            return [SearchResult(title="T", snippet="S", url="http://x.com")]

        svc = self._make_service()
        monkeypatch.setattr(svc, "_fetch", counting_fetch)

        svc.search("test query")
        svc.search("test query")

        assert call_count["n"] == 1

    def test_cache_hit_marks_cached_true(self, monkeypatch):
        """Cached response must set cached=True."""
        monkeypatch.setattr(
            WebSearchService,
            "_fetch",
            lambda self, q, n: [SearchResult(title="T", snippet="S", url="u")],
        )
        svc = self._make_service()
        svc.search("cached query")
        second = svc.search("cached query")
        assert second.cached is True

    def test_cache_expires_after_ttl(self, monkeypatch):
        """Expired cache entry must trigger a fresh _fetch call."""
        call_count = {"n": 0}

        def counting_fetch(query, max_results):
            call_count["n"] += 1
            return [SearchResult(title="T", snippet="S", url="u")]

        svc = WebSearchService(cache_ttl=1)  # 1-second TTL
        monkeypatch.setattr(svc, "_fetch", counting_fetch)

        svc.search("expiry query")
        # Manually age the cache entry beyond TTL
        key = svc._normalize_query("expiry query")
        ts, resp = svc._cache[key]
        svc._cache[key] = (ts - 2, resp)  # subtract 2s → past TTL

        svc.search("expiry query")
        assert call_count["n"] == 2

    def test_empty_query_returns_error_no_fetch(self, monkeypatch):
        """Blank/whitespace-only query must return error without calling _fetch."""
        fetch_called = {"called": False}

        def should_not_call(*args, **kwargs):
            fetch_called["called"] = True
            return []

        svc = self._make_service()
        monkeypatch.setattr(svc, "_fetch", should_not_call)

        resp = svc.search("   ")
        assert resp.error is not None
        assert not fetch_called["called"]


# ---------------------------------------------------------------------------
# Rate-limit test via SalesChatbot._maybe_enrich_with_search
# ---------------------------------------------------------------------------

class TestRateLimit:

    def _make_chatbot(self, monkeypatch):
        """Create a SalesChatbot with mocked provider and search disabled by default."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from chatbot.chatbot import SalesChatbot
        bot = SalesChatbot(provider_type=None, product_type=None, session_id=None)
        return bot

    def test_rate_limit_blocks_recent_search(self, monkeypatch):
        """_maybe_enrich_with_search returns None when called within rate-limit window."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from chatbot.chatbot import SalesChatbot
        bot = SalesChatbot(provider_type=None, product_type=None, session_id=None)

        # Set last search to 5 seconds ago (well within 30s window)
        bot._last_search_time = time.time() - 5
        # Force stage to objection and a money objection trigger phrase
        bot.flow_engine.current_stage = "objection"

        result = bot._maybe_enrich_with_search("can you show me proof of ROI")
        assert result is None

    def test_rate_limit_allows_after_window(self, monkeypatch):
        """_maybe_enrich_with_search is NOT blocked when last search was >30s ago."""
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        from chatbot.chatbot import SalesChatbot

        bot = SalesChatbot(provider_type=None, product_type=None, session_id=None)
        # Simulate search happening 60 seconds ago
        bot._last_search_time = time.time() - 60
        bot.flow_engine.current_stage = "objection"

        # Mock the search service to return a successful result
        from chatbot.web_search import SearchResponse, SearchResult
        bot._web_search.search = lambda query, max_results=3: SearchResponse(
            results=[SearchResult(title="T", snippet="Cost savings proven.", url="u")],
            query=query,
            cached=False,
        )

        result = bot._maybe_enrich_with_search("show me statistics on ROI")
        # Should not be None — rate limit cleared, trigger phrase matched
        assert result is not None
        assert "Cost savings proven." in result


# ---------------------------------------------------------------------------
# Trigger detection tests (pure functions)
# ---------------------------------------------------------------------------

_BASE_CONFIG = {
    "enabled": True,
    "trigger_phrases": ["proof", "statistics", "data", "evidence", "show me"],
    "trigger_objection_types": ["money", "fear", "think"],
}


class TestShouldTriggerWebSearch:

    def test_money_objection_at_objection_stage(self):
        result = should_trigger_web_search("objection", "money", "it's too expensive", _BASE_CONFIG)
        assert result is True

    def test_fear_objection_at_objection_stage(self):
        result = should_trigger_web_search("objection", "fear", "what if it doesn't work", _BASE_CONFIG)
        assert result is True

    def test_wrong_stage_no_trigger(self):
        """Objection type alone must not trigger if stage is not 'objection'."""
        result = should_trigger_web_search("logical", "money", "it's expensive", _BASE_CONFIG)
        assert result is False

    def test_explicit_phrase_triggers_any_stage(self):
        """'proof' in message triggers regardless of stage."""
        result = should_trigger_web_search("intent", None, "can you show me proof?", _BASE_CONFIG)
        assert result is True

    def test_disabled_config_never_triggers(self):
        config = {**_BASE_CONFIG, "enabled": False}
        result = should_trigger_web_search("objection", "money", "show me statistics", config)
        assert result is False

    def test_unknown_objection_type_no_trigger(self):
        result = should_trigger_web_search("objection", "unknown", "I don't know", _BASE_CONFIG)
        assert result is False


# ---------------------------------------------------------------------------
# Query building tests
# ---------------------------------------------------------------------------

class TestBuildSearchQuery:

    _TEMPLATES = {
        "money": "ROI statistics {keyword} cost savings",
        "fear": "success rate {keyword} risk case study",
        "explicit": "{keyword} facts data",
    }

    def test_money_uses_money_template(self):
        q = build_search_query("money", "cars", self._TEMPLATES)
        assert "cars" in q
        assert "ROI" in q

    def test_unknown_objection_falls_back_to_explicit(self):
        q = build_search_query("unknown", "insurance", self._TEMPLATES)
        assert "insurance" in q
        assert "facts" in q

    def test_none_objection_falls_back_to_explicit(self):
        q = build_search_query(None, "jewellery", self._TEMPLATES)
        assert "jewellery" in q

    def test_empty_product_type_uses_fallback_keyword(self):
        q = build_search_query("money", "", self._TEMPLATES)
        assert "product" in q
