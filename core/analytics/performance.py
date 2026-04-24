"""Minimal performance tracking."""

from collections import defaultdict
from typing import TypedDict


class ProviderStats(TypedDict):
    """Internal per-provider metric bucket."""

    requests: int
    total_latency_ms: float
    model: str | None


class PerformanceTracker:
    """Low-friction runtime metrics shim."""

    _provider_stats: defaultdict[str, ProviderStats] = defaultdict(
        lambda: {"requests": 0, "total_latency_ms": 0.0, "model": None}
    )

    @classmethod
    def log_stage_latency(cls, **kwargs) -> None:
        """Record latency without failing the main request path."""
        provider = str(kwargs.get("provider") or "unknown")
        latency_ms = kwargs.get("latency_ms")
        model = kwargs.get("model")

        stats = cls._provider_stats[provider]
        stats["requests"] += 1
        if isinstance(latency_ms, (int, float)):
            stats["total_latency_ms"] += float(latency_ms)
        if model:
            stats["model"] = model

        return None

    @classmethod
    def get_provider_stats(cls) -> dict[str, object]:
        """Return simple aggregate latency stats per provider."""
        providers: dict[str, dict[str, int | float | str | None]] = {}
        total_requests = 0

        for provider, stats in cls._provider_stats.items():
            requests = int(stats["requests"])
            total_latency_ms = float(stats["total_latency_ms"])
            total_requests += requests
            avg_latency_ms = round(total_latency_ms / requests, 1) if requests else None
            providers[provider] = {
                "requests": requests,
                "avg_latency_ms": avg_latency_ms,
                "model": stats["model"],
            }

        return {"total_requests": total_requests, "providers": providers}
