"""How long things take. Each span is one line in the timings stream:
name, when it started, ms, ok, its parent span's name and depth, and the request/session ids.

    with span("llm", provider="groq") as extra:   # add fields to `extra` while it runs
    @timed                                       # time every call, named <module>.<function>
"""

import functools
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

from . import store
from .context import current

_open: ContextVar[tuple] = ContextVar("open_spans", default=())


@contextmanager
def span(name: str, **fields):
    """Time the block. A block that raises is recorded with ok=false, then the error carries on."""
    outer = _open.get()
    token = _open.set((*outer, name))
    started = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    start = time.perf_counter()
    ok = True
    try:
        yield fields
    except BaseException:
        ok = False
        raise
    finally:
        ms = round((time.perf_counter() - start) * 1000, 1)
        _open.reset(token)
        store.append("timings", {
            **current(), "name": name, "ms": ms, "ok": ok,
            "parent": outer[-1] if outer else None, "depth": len(outer), "started": started, **fields,
        })


def timed(fn):
    """Decorator: a span around every call, named after the function (`core.` dropped)."""
    name = f"{fn.__module__.removeprefix('core.')}.{fn.__qualname__}"

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with span(name):
            return fn(*args, **kwargs)

    return wrapper
