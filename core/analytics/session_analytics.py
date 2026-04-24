"""Minimal session analytics store."""

from collections import Counter, defaultdict
from copy import deepcopy


class SessionAnalytics:
    """In-memory analytics sink used by routes and chatbot logic."""

    _events = defaultdict(list)

    @classmethod
    def _record(cls, session_id: str, event_type: str, **payload):
        if not session_id:
            return
        # Keep both keys so older readers using "type" and newer readers using
        # "event_type" stay in sync.
        cls._events[session_id].append(
            {"type": event_type, "event_type": event_type, **payload}
        )

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
        return deepcopy(cls._events.get(session_id, []))

    @classmethod
    def get_evaluation_summary(cls):
        """Return a small aggregate summary for analytics endpoints."""
        event_counts = Counter()

        for events in cls._events.values():
            for event in events:
                event_name = event.get("event_type") or event.get("type")
                if event_name:
                    event_counts[event_name] += 1

        return {
            "total_sessions": len(cls._events),
            "total_events": sum(event_counts.values()),
            "event_counts": dict(event_counts),
        }
