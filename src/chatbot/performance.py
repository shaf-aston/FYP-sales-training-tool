"""Per-stage LLM latency tracking. Metrics appended to metrics.jsonl."""

import json
import os
import time
import logging
from datetime import datetime
from threading import Lock
from .constants import MAX_METRICS_LINES, METRICS_KEEP_AFTER_ROTATION

logger = logging.getLogger(__name__)

METRICS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'metrics.jsonl')

# File-level lock — PerformanceTracker methods are called from request threads
lock = Lock()

# TTL cache for provider stats (avoid full file scan on every health check)
_stats_cache = {"data": {}, "ts": 0.0, "file": None}
_STATS_TTL = 30.0  # seconds

# In-memory line counter — avoids re-reading file on every write
_metrics_line_count: int = -1  # -1 = uninitialized


def _get_metrics_line_count() -> int:
    """Get current line count, initializing from file if needed."""
    global _metrics_line_count
    if _metrics_line_count < 0:
        try:
            if os.path.exists(METRICS_FILE):
                with open(METRICS_FILE, 'r') as f:
                    _metrics_line_count = sum(1 for _ in f)
            else:
                _metrics_line_count = 0
        except Exception:
            _metrics_line_count = 0
    return _metrics_line_count


def _increment_metrics_line_count() -> None:
    """Increment line count after successful write."""
    global _metrics_line_count
    if _metrics_line_count >= 0:
        _metrics_line_count += 1


def _reset_metrics_line_count(new_count: int) -> None:
    """Reset line count after rotation."""
    global _metrics_line_count
    _metrics_line_count = new_count


class PerformanceTracker:

    @staticmethod
    def log_stage_latency(session_id, stage, strategy, latency_ms, provider, model, user_message_length=0, bot_response_length=0):
        """Append a latency metric record to metrics.jsonl (uses in-memory line count)."""
        metric = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "stage": stage,
            "strategy": strategy,
            "provider": provider,
            "model": model,
            "latency_ms": round(latency_ms, 1),
            "user_msg_len": user_message_length,
            "bot_resp_len": bot_response_length
        }
        with lock:
            try:
                current_count = _get_metrics_line_count()

                # Rotate if exceeds max lines
                if current_count >= MAX_METRICS_LINES and os.path.exists(METRICS_FILE):
                    with open(METRICS_FILE, 'r') as f:
                        lines = f.readlines()
                    keep_lines = lines[-METRICS_KEEP_AFTER_ROTATION:]
                    with open(METRICS_FILE, 'w') as f:
                        f.writelines(keep_lines)
                    _reset_metrics_line_count(len(keep_lines))

                with open(METRICS_FILE, 'a') as f:
                    f.write(json.dumps(metric) + '\n')
                _increment_metrics_line_count()
            except Exception as e:
                logger.warning("Failed to record metric: %s", e)

    @staticmethod
    def get_provider_stats():
        """Aggregate metrics by provider (cached with TTL)."""
        now = time.time()
        with lock:
            # Return cached stats if TTL not expired
            if _stats_cache["file"] == METRICS_FILE and now - _stats_cache["ts"] < _STATS_TTL:
                return dict(_stats_cache["data"])

            # Scan metrics file and rebuild cache
            stats = {}
            try:
                with open(METRICS_FILE, 'r') as f:
                    for line in f:
                        try:
                            metric = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        provider = metric.get("provider")
                        if provider:
                            if provider not in stats:
                                stats[provider] = {"count": 0, "total_latency": 0}
                            stats[provider]["count"] += 1
                            stats[provider]["total_latency"] += metric.get("latency_ms", 0)
            except FileNotFoundError:
                pass

            # Calculate averages
            for provider, data in stats.items():
                data["avg_latency_ms"] = data["total_latency"] / data["count"] if data["count"] > 0 else 0

            # Update cache
            _stats_cache["data"] = stats
            _stats_cache["ts"] = now
            _stats_cache["file"] = METRICS_FILE

        return stats

    @staticmethod
    def get_session_metrics(session_id):
        """Retrieve all metrics for a specific session."""
        session_metrics = []
        with lock:
            try:
                with open(METRICS_FILE, 'r') as f:
                    for line in f:
                        try:
                            metric = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if metric.get("session_id") == session_id:
                            session_metrics.append(metric)
            except FileNotFoundError:
                pass
        return session_metrics
