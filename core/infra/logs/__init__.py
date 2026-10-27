"""Everything the app writes down about itself, one folder per stream under the logs dir:

    events/    what happened in each chat (session_start, conversation_turn, session_score, ...)
    timings/   how long each request took, and each step inside it (spans nest: request > turn > AI call)
    feedback/  ratings and comments learners send

Each file is one UTC day of JSONL. `store.py` is the only writer; the other modules only shape their records.
Read them with `python scripts/timings_report.py` and `python scripts/show_convo.py`.
"""

from core.infra.logs.context import request_context, tag_session
from core.infra.logs.events import SessionAnalytics
from core.infra.logs.feedback import save_feedback
from core.infra.logs.timing import span, timed

__all__ = ["SessionAnalytics", "request_context", "save_feedback", "span", "tag_session", "timed"]
