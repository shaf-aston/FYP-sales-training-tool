"""Rate limiting, input validation and session management"""

import logging
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from core.constants import (
    API_HEADERS,
    CLEANUP_INTERVAL_SECONDS,
    CSP,
    DEFAULT_TRUST_PROXY_HEADERS,
    MAX_FIELD_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_SESSIONS,
    MAX_TURN_NUMBER,
    RATE_LIMITS,
    SECURITY_HEADERS,
    SESSION_ID_MAX_CHARS,
    SESSION_ID_MIN_CHARS,
    SESSION_IDLE_MINUTES,
)
from core.env import env_flag
from .messages import (
    FIELD_NOT_TEXT,
    FIELD_TOO_LONG,
    INVALID_SESSION_ID,
    MESSAGE_REQUIRED,
    MESSAGE_TOO_LONG,
    NO_DATA,
    RATE_LIMIT_ERROR,
    SESSION_ID_REQUIRED,
    UNKNOWN_FIELD,
    UNKNOWN_FIELDS,
)

logger = logging.getLogger(__name__)


SESSION_ID_PATTERN = re.compile(rf"^[A-Za-z0-9_-]{{{SESSION_ID_MIN_CHARS},{SESSION_ID_MAX_CHARS}}}$")
CONTENT_SECURITY_POLICY = "; ".join(f"{name} {' '.join(sources)}" for name, sources in CSP.items())


class RateLimiter:
    """Track request counts per IP/bucket"""

    def __init__(self, limits: Dict[str, Tuple[int, int]]):
        self.limits = limits
        self._store: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_limited(self, ip: str, bucket: str) -> bool:
        max_req, window = self.limits[bucket]
        key = f"{bucket}:{ip}"
        now = time.time()

        with self._lock:
            dq = self._store.get(key)
            if dq is None:
                dq = deque()
                self._store[key] = dq

            while dq and now - dq[0] > window:
                dq.popleft()

            if len(dq) >= max_req:
                return True

            dq.append(now)
            return False


def require_rate_limit(bucket: str) -> Callable:
    """Rate-limit decorator by client IP"""

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import current_app, jsonify, request

            if current_app.config.get("TESTING"):
                return f(*args, **kwargs)

            ip = ClientIPExtractor.get_ip(request)
            if _rate_limiter is not None and _rate_limiter.is_limited(ip, bucket):
                return jsonify({"error": RATE_LIMIT_ERROR}), 429

            return f(*args, **kwargs)

        return wrapper

    return decorator


_rate_limiter: Optional[RateLimiter] = None


class SecurityHeadersMiddleware:
    """Attach security headers to every Flask response"""

    @staticmethod
    def apply(response):
        response.headers.update(SECURITY_HEADERS)
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        if response.direct_passthrough:
            return response
        from flask import request
        if request.path.startswith("/api/"):
            response.headers.update(API_HEADERS)
        return response


class InputValidator:
    """Message and knowledge field validation"""

    @staticmethod
    def validate_message(
        text: str,
        max_length: int = MAX_MESSAGE_LENGTH,
    ) -> Tuple[Optional[str], Optional[Tuple]]:
        from flask import jsonify

        text = text.strip()

        if not text:
            return None, (jsonify({"error": MESSAGE_REQUIRED}), 400)

        if len(text) > max_length:
            return None, (
                jsonify({"error": MESSAGE_TOO_LONG.format(max_length=max_length)}),
                400,
            )

        return text, None

    @staticmethod
    def validate_session_id(session_id: Any) -> Optional[Tuple]:
        from flask import jsonify

        if not isinstance(session_id, str) or not session_id.strip():
            return jsonify({"error": SESSION_ID_REQUIRED}), 400

        if not SESSION_ID_PATTERN.fullmatch(session_id.strip()):
            return jsonify({"error": INVALID_SESSION_ID}), 400

        return None

    @staticmethod
    def validate_knowledge_field(
        key: str,
        value: Any,
        allowed_fields: set,
        max_field_length: int = MAX_FIELD_LENGTH,
    ) -> Optional[Tuple]:
        from flask import jsonify

        if key not in allowed_fields:
            return jsonify({"error": UNKNOWN_FIELD.format(key=key)}), 400

        if not isinstance(value, str):
            return jsonify({"error": FIELD_NOT_TEXT.format(key=key)}), 400

        if len(value) > max_field_length:
            return jsonify({"error": FIELD_TOO_LONG.format(key=key, max_length=max_field_length)}), 400

        return None

    @staticmethod
    def validate_knowledge_data(
        data: Any,
        allowed_fields: set,
        max_field_length: int = MAX_FIELD_LENGTH,
    ) -> Optional[Tuple]:
        from flask import jsonify

        if not data or not isinstance(data, dict):
            return jsonify({"error": NO_DATA}), 400

        unknown = set(data.keys()) - allowed_fields
        if unknown:
            return jsonify({"error": UNKNOWN_FIELDS.format(keys=", ".join(unknown))}), 400

        for key, value in data.items():
            error = InputValidator.validate_knowledge_field(key, value, allowed_fields, max_field_length)
            if error:
                return error

        return None

    @staticmethod
    def normalize_provider(raw: Any) -> str | None:
        if not isinstance(raw, str):
            return None
        v = raw.strip().lower()
        return None if (not v or v == "auto") else v

    @staticmethod
    def parse_positive_int(raw: Any, maximum: int = MAX_TURN_NUMBER) -> int | None:
        """Whole number above zero, or None. Rejects floats, bools and huge values."""
        if isinstance(raw, bool) or isinstance(raw, float):
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        return value if 0 < value <= maximum else None


class ClientIPExtractor:
    """Extract the real client IP address"""

    @staticmethod
    def get_ip(request_obj) -> str:
        from flask import current_app

        trust_proxy_headers = current_app.config.get(
            "TRUST_PROXY_HEADERS",
            env_flag("TRUST_PROXY_HEADERS", DEFAULT_TRUST_PROXY_HEADERS),
        )
        forwarded = request_obj.headers.get("X-Forwarded-For") if trust_proxy_headers else None
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request_obj.remote_addr or "unknown"


class SessionSecurityManager:
    """In-memory session store with automatic idle cleanup"""

    def __init__(
        self,
        max_sessions: int = MAX_SESSIONS,
        idle_minutes: int = SESSION_IDLE_MINUTES,
        cleanup_interval: int = CLEANUP_INTERVAL_SECONDS,
        manager_name: str = "sessions",
    ):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.idle_minutes = idle_minutes
        self.cleanup_interval = cleanup_interval
        self.manager_name = manager_name
        self._cleanup_started = False

    def get(self, session_id: str) -> Optional[Any]:
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry:
                entry["ts"] = datetime.now()
                return entry["bot"]
        return None

    def set(self, session_id: str, chatbot: Any) -> None:
        with self._lock:
            self._sessions[session_id] = {"bot": chatbot, "ts": datetime.now()}

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def can_create(self) -> bool:
        with self._lock:
            return len(self._sessions) < self.max_sessions

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _cleanup_expired(self) -> int:
        with self._lock:
            now = datetime.now()
            max_idle = timedelta(minutes=self.idle_minutes)
            expired_ids = [
                sid for sid, s in self._sessions.items() if now - s["ts"] > max_idle
            ]
            for sid in expired_ids:
                del self._sessions[sid]
            if expired_ids:
                logger.info("Cleaned up %d idle %s", len(expired_ids), self.manager_name)
            return len(expired_ids)

    def start_background_cleanup(self) -> None:
        with self._lock:
            if self._cleanup_started:
                return
            self._cleanup_started = True

        def cleanup_loop():
            while True:
                try:
                    time.sleep(self.cleanup_interval)
                    self._cleanup_expired()
                except Exception as e:
                    logger.error("Cleanup thread error: %s", e)

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logger.info("Started cleanup thread for %s (interval: %ss)", self.manager_name, self.cleanup_interval)


def initialize_security(
    app_logger=None,
) -> Tuple[RateLimiter, SessionSecurityManager]:
    """Initialize security singletons (call once at startup)"""
    global _rate_limiter

    if app_logger:
        logger.handlers = app_logger.handlers
        logger.setLevel(app_logger.level)

    _rate_limiter = RateLimiter(RATE_LIMITS)
    session_manager = SessionSecurityManager(
        max_sessions=MAX_SESSIONS,
        idle_minutes=SESSION_IDLE_MINUTES,
        cleanup_interval=CLEANUP_INTERVAL_SECONDS,
        manager_name="chat sessions",
    )
    return _rate_limiter, session_manager
