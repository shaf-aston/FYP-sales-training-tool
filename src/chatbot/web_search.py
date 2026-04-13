"""Web search enrichment. Grabs external context for objection reframes"""

import logging
import re
import time
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
    """TTL-cached search. Always returns SearchResponse, never raises"""

    def __init__(self, cache_ttl: int = 1800):
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[float, SearchResponse]] = {}

    def search(self, query: str, max_results: int = 3) -> SearchResponse:
        """Run a search. Never raises; errors go in SearchResponse.error"""
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
        """Hit DuckDuckGo. Raises on network failure"""
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    SearchResult(
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        url=r.get("href", ""),
                    )
                )
        return results

    def _normalize_query(self, query: str) -> str:
        """Strip special chars, cap at 100 chars"""
        query = re.sub(r"[^\w\s'-]", " ", query).strip()
        query = re.sub(r"\s+", " ", query)
        return query[:100]

    def _cache_get(self, key: str) -> SearchResponse | None:
        """Grab cached response if still fresh"""
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
