"""Server logging: switch it on once at start-up, and time every API request.

Each /api request gets a request id, carries the learner's session id, and becomes the outermost span in the
timings stream; everything timed inside it nests under it. The browser sees the total in `Server-Timing`
(devtools → Network → Timing) and the id in `X-Request-ID`.
"""

import logging
import time
import uuid

from core.constants import LOG_LEVEL, SESSION_ID_MAX_CHARS
from core.logs import request_context, span

logger = logging.getLogger(__name__)
_MAX_PATH_CHARS = 200  # paths are learner-controlled; keep log lines short


def configure_logging() -> None:
    """Send every module's log lines to stderr (the service's journal). Call before the Flask app exists."""
    logging.basicConfig(level=LOG_LEVEL, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")


class RequestLog:
    """WSGI middleware: `app.wsgi_app = RequestLog(app.wsgi_app)`."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if not path.startswith("/api/"):
            return self.wsgi_app(environ, start_response)  # page files are not worth a line each

        request_id = uuid.uuid4().hex[:12]
        route = f"{environ.get('REQUEST_METHOD', '?')} {path[:_MAX_PATH_CHARS]}"
        session_id = (environ.get("HTTP_X_SESSION_ID") or "")[:SESSION_ID_MAX_CHARS]
        start = time.perf_counter()

        with request_context(request_id=request_id, session_id=session_id), span("request", route=route) as extra:

            def timed_start(status, headers, exc_info=None):
                ms = (time.perf_counter() - start) * 1000
                extra["status"] = int(status.split()[0])
                headers += [("Server-Timing", f"app;dur={ms:.1f}"), ("X-Request-ID", request_id)]
                logger.info("%s %d %.0f ms request=%s session=%s", route, extra["status"], ms, request_id, session_id or "-")
                return start_response(status, headers, exc_info)

            return self.wsgi_app(environ, timed_start)
