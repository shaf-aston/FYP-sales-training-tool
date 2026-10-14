"""Session analytics events: one log line each, plus an optional JSONL file.

The log is the durable record (the host keeps it). Set METRICS_JSONL_PATH to also append each event to a
file for quick local inspection. Nothing is kept in memory.
"""

import json
import logging

from ..env import env_str

logger = logging.getLogger(__name__)


class SessionAnalytics:
    @staticmethod
    def record(*, session_id: str, event: str, **payload) -> None:
        """Log one event, and append it to the JSONL file when METRICS_JSONL_PATH is set."""
        if not session_id:
            return
        line = json.dumps({"session_id": session_id, "event_type": event, **payload}, ensure_ascii=False, default=str)

        path = (env_str("METRICS_JSONL_PATH") or "").strip()
        if path:
            try:  # best effort: a convenience for local use, never worth failing a turn
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                logger.debug("metrics_jsonl_write_failed path=%s", path, exc_info=True)

        logger.info("session_analytics %s", line)
