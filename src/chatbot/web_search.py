"""Web search enrichment service — fetches external validation context for objection handling.

Stateless with respect to sessions: caller (SalesChatbot) owns rate-limit tracking.
All session-specific state (last_search_time) lives in SalesChatbot, not here.
"""

import re
import time
import logging
from dataclasses import dataclass, field, replace

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str


@dataclass
class SearchResponse:
    results: list[SearchResult] = field(default_factory=list)
    query: str = ""
    cached: bool = False
    error: str | None = None


class WebSearchService:
    """Fetches web search results for objection-handling context.

    Cache: TTL-based dict keyed by normalized query — no external dependency.
    Graceful: always returns SearchResponse, never raises.

    Args:
        cache_ttl: Seconds before a cached result expires (default: 1800 = 30 min).
    """

    def __init__(self, cache_ttl: int = 1800):
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, SearchResponse]] = {}

    def search(self, query: str, max_results: int = 3) -> SearchResponse:
        """Return search results for query. Returns SearchResponse(error=...) on failure."""
        query = self._normalize_query(query)
        if not query:
            return SearchResponse(query=query, error="empty query after normalization")

        cached = self._cache_get(query)
        if cached is not None:
            return cached

        try:
            results = self._fetch(query, max_results)
            response = SearchResponse(results=results, query=query, cached=False)
            self._cache_set(query, response)
            return response
        except Exception as e:
            logger.warning("Web search failed for query %r: %s", query, e)
            return SearchResponse(query=query, error=str(e))

    def _fetch(self, query: str, max_results: int) -> list[SearchResult]:
        """Call the underlying search library. Raises on network failure (caught by search())."""
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                    url=r.get("href", ""),
                ))
        return results

    def _normalize_query(self, query: str) -> str:
        """Strip special characters and enforce max length."""
        query = re.sub(r"[^\w\s'-]", " ", query).strip()
        query = re.sub(r"\s+", " ", query)
        return query[:100]

    def _cache_get(self, key: str) -> SearchResponse | None:
        """Return cached response if within TTL, else None."""
        entry = self._cache.get(key)
        if not entry:
            return None
        timestamp, response = entry
        if time.time() - timestamp > self._cache_ttl:
            del self._cache[key]
            return None
        return replace(response, cached=True)

    def _cache_set(self, key: str, response: SearchResponse) -> None:
        self._cache[key] = (time.time(), response)
