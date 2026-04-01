"""Per-stage LLM latency tracking. Metrics appended to metrics.jsonl."""

import os
import time
import logging
from datetime import datetime
from ..constants import MAX_METRICS_LINES, METRICS_KEEP_AFTER_ROTATION
from .jsonl_store import JSONLWriter

logger = logging.getLogger(__name__)

METRICS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'metrics.jsonl')

_writer = JSONLWriter(METRICS_FILE, MAX_METRICS_LINES, METRICS_KEEP_AFTER_ROTATION)

# TTL cache for provider stats (avoid full file scan on every health check)
_stats_cache: dict = {"data": {}, "ts": 0.0}
_STATS_TTL = 30.0  # seconds


def _get_writer() -> JSONLWriter:
    """Return the active writer. Indirection allows test monkeypatching."""
    return _writer


class PerformanceTracker:

    @staticmethod
    def log_stage_latency(session_id, stage, strategy, latency_ms, provider, model, user_message_length=0, bot_response_length=0):
        """Append a latency metric record to metrics.jsonl."""
        _get_writer().append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "stage": stage,
            "strategy": strategy,
            "provider": provider,
            "model": model,
            "latency_ms": round(latency_ms, 1),
            "user_msg_len": user_message_length,
            "bot_resp_len": bot_response_length,
        })

    @staticmethod
    def get_provider_stats():
        """Aggregate metrics by provider (cached with TTL)."""
        now = time.time()
        if now - _stats_cache["ts"] < _STATS_TTL and _stats_cache["data"]:
            return dict(_stats_cache["data"])

        stats: dict = {}
        for metric in _get_writer().read_all():
            provider = metric.get("provider")
            if provider:
                if provider not in stats:
                    stats[provider] = {"count": 0, "total_latency": 0}
                stats[provider]["count"] += 1
                stats[provider]["total_latency"] += metric.get("latency_ms", 0)

        for data in stats.values():
            data["avg_latency_ms"] = data["total_latency"] / data["count"] if data["count"] > 0 else 0

        _stats_cache["data"] = stats
        _stats_cache["ts"] = now
        return stats

    @staticmethod
    def get_session_metrics(session_id):
        """Retrieve all metrics for a specific session."""
        return _get_writer().read_filtered("session_id", session_id)
