"""Session analytics: what happened in each chat, one record per event in the events stream."""

from core.infra.logs import store
from core.infra.logs.context import current


class SessionAnalytics:
    @staticmethod
    def record(*, session_id: str, event: str, **payload) -> None:
        """Keep one event for this session. Events without a session are dropped."""
        if not session_id:
            return
        store.write("events", {**current(), "session_id": session_id, "event_type": event, **payload})
