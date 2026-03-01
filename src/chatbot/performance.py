"""Performance tracking for user study metrics (temporary JSON file storage).

Collects per-stage latency, provider usage, strategy paths for analysis.
Metrics stored in metrics.jsonl (JSONL format for streaming append).

Functions:
- log_stage_latency: Record LLM response time per stage
- log_error: Log error events with context
- get_provider_stats: Aggregate latency by provider
- get_session_metrics: Retrieve all metrics for a session
- get_turn_latency_summary: Get latest turn latency for UI display
"""
import json
import os
from datetime import datetime
from threading import Lock

METRICS_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'metrics.jsonl')
lock = Lock()

class PerformanceTracker:
    @staticmethod
    def log_stage_latency(session_id, stage, strategy, latency_ms, provider, model, user_message_length=0, bot_response_length=0):
        """Log LLM latency metrics for a conversation turn.
        
        Args:
            session_id: Unique session identifier
            stage: Current FSM stage (intent, logical, emotional, pitch, objection)
            strategy: Flow strategy (consultative, transactional)
            latency_ms: LLM response time in milliseconds
            provider: LLM provider name (groq, ollama)
            model: Model identifier
            user_message_length: Character count of user input
            bot_response_length: Character count of bot output
        """
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
    
    @staticmethod
    def get_turn_latency_summary(session_id):
        """Get latency from last recorded turn in session (for UI display)."""
        with lock:
            try:
                last_metric = None
                with open(METRICS_FILE, 'r') as f:
                    for line in f:
                        metric = json.loads(line)
                        if metric.get("session_id") == session_id:
                            last_metric = metric
                if last_metric and "latency_ms" in last_metric:
                    return {
                        "latency_ms": round(last_metric["latency_ms"], 1),
                        "provider": last_metric.get("provider", ""),
                        "model": last_metric.get("model", ""),
                        "input_length": last_metric.get("user_msg_len", 0),
                        "output_length": last_metric.get("bot_resp_len", 0)
                    }
            except FileNotFoundError:
                pass
        return None
