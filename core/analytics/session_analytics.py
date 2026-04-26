"""Persistent session analytics store."""

from collections import Counter, defaultdict
from copy import deepcopy
import json
import logging
import os
import re
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ANALYTICS_DIR = os.path.join(ROOT_DIR, "analytics")
SESSION_EVENTS_DIR = os.path.join(ANALYTICS_DIR, "sessions")

_LOCK = Lock()


def _ensure_events_dir() -> None:
    os.makedirs(SESSION_EVENTS_DIR, exist_ok=True)


def _is_valid_session_id(session_id: str) -> bool:
    if not isinstance(session_id, str) or not session_id:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_-]+", session_id))


def _get_safe_path(session_id: str) -> str | None:
    if not _is_valid_session_id(session_id):
        logger.warning("Rejected invalid analytics session_id: %r", session_id)
        return None

    _ensure_events_dir()
    filepath = os.path.abspath(os.path.join(SESSION_EVENTS_DIR, f"{session_id}.jsonl"))
    if not filepath.startswith(os.path.abspath(SESSION_EVENTS_DIR) + os.sep):
        logger.warning("Blocked analytics path traversal attempt: %r", filepath)
        return None

    return filepath


def _load_events_from_disk(session_id: str) -> list[dict[str, Any]]:
    filepath = _get_safe_path(session_id)
    if filepath is None or not os.path.exists(filepath):
        return []

    events: list[dict[str, Any]] = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping corrupted analytics line for %s", session_id)
                    continue
                if isinstance(event, dict):
                    events.append(event)
    except OSError as e:
        logger.error("Failed to load analytics for %s: %s", session_id, e)
        return []
    return events


class SessionAnalytics:
    """In-memory analytics cache with durable JSONL persistence."""

    _events = defaultdict(list)

    @classmethod
    def _record(cls, session_id: str, event_type: str, **payload):
        if not session_id:
            return

        # Keep both keys so older readers using "type" and newer readers using
        # "event_type" stay in sync.
        event = {"type": event_type, "event_type": event_type, **payload}

        with _LOCK:
            cls._events[session_id].append(event)

            filepath = _get_safe_path(session_id)
            if filepath is None:
                return

            try:
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            except OSError as e:
                logger.error("Failed to persist analytics for %s: %s", session_id, e)

    @classmethod
    def record_session_start(cls, session_id: str, **payload):
        cls._record(session_id, "session_start", **payload)

    @classmethod
    def record_stage_transition(cls, session_id: str, **payload):
        cls._record(session_id, "stage_transition", **payload)

    @classmethod
    def record_intent_classification(cls, session_id: str, **payload):
        cls._record(session_id, "intent_classification", **payload)

    @classmethod
    def record_objection_classified(cls, session_id: str, **payload):
        cls._record(session_id, "objection_classified", **payload)

    @classmethod
    def record_strategy_switch(cls, session_id: str, **payload):
        cls._record(session_id, "strategy_switch", **payload)

    @classmethod
    def get_session_analytics(cls, session_id: str):
        with _LOCK:
            cached = cls._events.get(session_id)
            if cached is not None:
                return deepcopy(cached)

        events = _load_events_from_disk(session_id)
        if events:
            with _LOCK:
                cls._events[session_id] = deepcopy(events)
        return events

    @classmethod
    def get_evaluation_summary(cls):
        """Return a small aggregate summary for analytics endpoints."""
        event_counts = Counter()
        session_ids = set()

        if os.path.isdir(SESSION_EVENTS_DIR):
            for path in Path(SESSION_EVENTS_DIR).glob("*.jsonl"):
                session_ids.add(path.stem)

        with _LOCK:
            session_ids.update(cls._events.keys())

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
