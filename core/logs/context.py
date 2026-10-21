"""Who the current work is for. Every record made inside one request carries the same request and session ids."""

from contextlib import contextmanager
from contextvars import ContextVar

_ids: ContextVar[dict] = ContextVar("log_ids", default={})


def current() -> dict:
    """The ids of the request in progress (empty outside one)."""
    return _ids.get()


def tag_session(session_id: str) -> None:
    """A session born inside this request: tag the rest of the request with it (no-op outside a request)."""
    ids = _ids.get()
    if ids and session_id:
        ids["session_id"] = session_id


@contextmanager
def request_context(**ids):
    """Tag everything recorded inside this block with `ids` (unset values are dropped)."""
    token = _ids.set({**_ids.get(), **{k: v for k, v in ids.items() if v}})
    try:
        yield
    finally:
        _ids.reset(token)
