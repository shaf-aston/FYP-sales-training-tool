"""Per-stage LLM latency tracking. Metrics appended to metrics.jsonl."""
import json
import os
from datetime import datetime
from threading import Lock

METRICS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'metrics.jsonl')
lock = Lock()

class PerformanceTracker:
    @staticmethod
    def log_stage_latency(session_id, stage, strategy, latency_ms, provider, model, user_message_length=0, bot_response_length=0):
        """Append a latency metric record to metrics.jsonl."""
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
                with open(METRICS_FILE, 'a') as f:
                    f.write(json.dumps(metric) + '\n')
            except Exception:
                pass

    @staticmethod
    def get_provider_stats():
        """Aggregate metrics by provider."""
        stats = {}
        with lock:
            try:
                with open(METRICS_FILE, 'r') as f:
                    for line in f:
                        metric = json.loads(line)
                        provider = metric.get("provider")
                        if provider:
                            if provider not in stats:
                                stats[provider] = {"count": 0, "total_latency": 0}
                            stats[provider]["count"] += 1
                            stats[provider]["total_latency"] += metric.get("latency_ms", 0)
            except FileNotFoundError:
                pass
        for provider, data in stats.items():
            data["avg_latency_ms"] = data["total_latency"] / data["count"] if data["count"] > 0 else 0
        return stats

    @staticmethod
    def get_session_metrics(session_id):
        """Retrieve all metrics for a specific session."""
        session_metrics = []
        with lock:
            try:
                with open(METRICS_FILE, 'r') as f:
                    for line in f:
                        metric = json.loads(line)
                        if metric.get("session_id") == session_id:
                            session_metrics.append(metric)
            except FileNotFoundError:
                pass
        return session_metrics
