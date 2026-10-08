"""Session analytics events (in-memory + logs, optional JSONL sink).

Design goals:
- Keep the runtime behavior simple: events live in memory for this process.
- Always mirror events into application logs (Render-friendly durability).
- Optionally (local/dev) mirror events into a JSONL file for quick inspection.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import json
import logging
from threading import Lock

from ..env import env_str

logger = logging.getLogger(__name__)

_LOCK = Lock()


class SessionAnalytics:
    """In-memory analytics cache that mirrors events into application logs."""

    _events = defaultdict(list)

    @classmethod
    def _jsonl_path(cls) -> str | None:
        """Read the optional JSONL sink path from the environment."""
        path = env_str("METRICS_JSONL_PATH")
        if not path:
            return None
        path = path.strip()
        return path or None

    @classmethod
    def _write_jsonl(cls, entry: dict) -> None:
        """Append one analytics entry to the optional JSONL sink."""
        path = cls._jsonl_path()
        if not path:
            return
        # Best-effort: this is a convenience sink for local/dev, not core functionality.
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            logger.debug("metrics_jsonl_write_failed path=%s", path, exc_info=True)

    @classmethod
    def record(cls, *, session_id: str, event: str, **payload) -> None:
        """Store one analytics event in memory, logs, and optional JSONL."""
        if not session_id:
            return

        entry = {"event_type": event, **payload}

        with _LOCK:
            cls._events[session_id].append(entry)

        cls._write_jsonl({"session_id": session_id, **entry})

        logger.info(
            "session_analytics %s",
            json.dumps(
                {"session_id": session_id, **entry},
                ensure_ascii=False,
                default=str,
            ),
        )

    @classmethod
    def get_session_analytics(cls, session_id: str):
        """Return a safe copy of all analytics events for one session."""
        with _LOCK:
            return deepcopy(cls._events.get(session_id, []))

    @classmethod
    def get_evaluation_summary(cls):
        """Return aggregate stats for the current process only."""

        event_counts = Counter()
        with _LOCK:
            session_ids = list(cls._events.keys())

        for session_id in sorted(session_ids):
            for event in cls.get_session_analytics(session_id):
                event_name = event.get("event_type")
                if event_name:
                    event_counts[event_name] += 1

        return {
            "total_sessions": len(session_ids),
            "total_events": sum(event_counts.values()),
            "event_counts": dict(event_counts),
        }
