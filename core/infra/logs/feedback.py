"""Learner feedback: one record per rating or comment, tied to the session it came from."""

from core.infra.logs import store
from core.infra.logs.context import current


def save_feedback(*, rating: int | None, comment: str | None, page: str) -> None:
    """Keep one already-validated piece of feedback in the feedback stream."""
    store.write("feedback", {**current(), "rating": rating, "comment": comment, "page": page})
