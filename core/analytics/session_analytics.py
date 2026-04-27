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
import os
from threading import Lock

logger = logging.getLogger(__name__)

_LOCK = Lock()


class SessionAnalytics:
    """In-memory analytics cache that mirrors events into application logs."""

    _events = defaultdict(list)

    @classmethod
    def _jsonl_path(cls) -> str | None:
        """Read the optional JSONL sink path from the environment."""
        path = os.environ.get("METRICS_JSONL_PATH")
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
        """Record an analytics event.

        Prefer this method in new code. Legacy `record_*` helpers remain for callers/tests.
        """
        cls._record(session_id, event, **payload)

    @classmethod
    def _record(cls, session_id: str, event_type: str, **payload) -> None:
        """Store one analytics event in memory, logs, and optional JSONL."""
        if not session_id:
            return

        # Keep both keys for backward compatibility with any log parsers.
        event = {"event_type": event_type, "type": event_type, **payload}

        with _LOCK:
            cls._events[session_id].append(event)

        cls._write_jsonl({"session_id": session_id, **event})

        logger.info(
            "session_analytics %s",
            json.dumps(
                {"session_id": session_id, **event},
                ensure_ascii=False,
                default=str,
            ),
        )

    @classmethod
    def record_session_start(cls, session_id: str, **payload):
        """Record the first event for a new chatbot session."""
        cls._record(session_id, "session_start", **payload)

    @classmethod
    def record_stage_transition(cls, session_id: str, **payload):
        """Record a stage change inside the conversation flow."""
        cls._record(session_id, "stage_transition", **payload)

    @classmethod
    def record_intent_classification(cls, session_id: str, **payload):
        """Record the latest detected intent level for the user."""
        cls._record(session_id, "intent_classification", **payload)

    @classmethod
    def record_objection_classified(cls, session_id: str, **payload):
        """Record the objection type detected on a user turn."""
        cls._record(session_id, "objection_classified", **payload)

    @classmethod
    def record_strategy_switch(cls, session_id: str, **payload):
        """Record a switch between conversation strategies."""
        cls._record(session_id, "strategy_switch", **payload)

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
                event_name = event.get("event_type") or event.get("type")
                if event_name:
                    event_counts[event_name] += 1

        return {
            "total_sessions": len(session_ids),
            "total_events": sum(event_counts.values()),
            "event_counts": dict(event_counts),
        }
