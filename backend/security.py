"""Rate limiting, input validation and session management"""

import hmac
import logging
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from core import constants as limits
from . import settings
from .messages import RATE_LIMIT_ERROR

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security thresholds and limits in one place"""

    SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

    # Session management
    MAX_SESSIONS = limits.MAX_SESSIONS
    SESSION_IDLE_MINUTES = limits.SESSION_IDLE_MINUTES
    CLEANUP_INTERVAL_SECONDS = limits.CLEANUP_INTERVAL_SECONDS
    TRUST_PROXY_HEADERS = False

    # Message validation
    MAX_MESSAGE_LENGTH = limits.MAX_MESSAGE_LENGTH
    MAX_FIELD_LENGTH = limits.MAX_FIELD_LENGTH

    # Rate limiting: (max_requests, window_seconds)
    RATE_LIMITS = limits.RATE_LIMITS

    # Security headers
    SECURITY_HEADERS = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-XSS-Protection": "1; mode=block",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(self), geolocation=()",
    }

    @staticmethod
    def content_security_policy() -> str:
        return (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://js.puter.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "media-src 'self' data: blob: https://puter.com https://*.puter.com; "
            "connect-src 'self' https://js.puter.com https://puter.com https://*.puter.com; "
            "font-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )


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


def require_privileged_mutation(f: Callable) -> Callable:
    """Guard FSM mutation routes behind an optional admin token.

    Enabled by REQUIRE_ADMIN_FOR_STAGE_MUTATION env var (or app config).
    Token must be supplied in X-Admin-Token or Authorization: Bearer <token>.
    Bypassed when Flask TESTING is true.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        from flask import current_app, jsonify, request

        require_admin = settings.require_admin_for_stage_mutation(current_app.config)

        if not require_admin or current_app.config.get("TESTING"):
            return f(*args, **kwargs)

        if not has_valid_admin_token(request, current_app.config):
            logger.warning("Blocked privileged mutation path=%s", request.path)
            return jsonify({"error": "Admin token required"}), 403

        return f(*args, **kwargs)

    return wrapper


def has_valid_admin_token(request_obj, config_obj) -> bool:
    admin_token = settings.admin_token() or config_obj.get("ADMIN_TOKEN")
    token = request_obj.headers.get("X-Admin-Token") or request_obj.headers.get("Authorization", "")
    if isinstance(token, str) and token.lower().startswith("bearer "):
        token = token.split(None, 1)[1]
    if not admin_token or not token:
        logger.debug(
            "Auth check failed: admin_token_configured=%s, token_supplied=%s",
            bool(admin_token),
            bool(token),
        )
        return False
    result = hmac.compare_digest(str(token), str(admin_token))
    logger.debug(f"Auth check: token_valid={result}, admin_token_set={bool(admin_token)}")
    return result


class SecurityHeadersMiddleware:
    """Attach security headers to every Flask response"""

    @staticmethod
    def apply(response):
        for key, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[key] = value
        response.headers["Content-Security-Policy"] = SecurityConfig.content_security_policy()
        if response.direct_passthrough:
            return response
        from flask import request
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


class InputValidator:
    """Message and knowledge field validation"""

    @staticmethod
    def validate_message(
        text: str,
        max_length: int = SecurityConfig.MAX_MESSAGE_LENGTH,
    ) -> Tuple[Optional[str], Optional[Tuple]]:
        from flask import jsonify

        text = text.strip()

        if not text:
            return None, (jsonify({"error": "Message required"}), 400)

        if len(text) > max_length:
            return None, (
                jsonify({"error": f"Message too long (max {max_length} characters)"}),
                400,
            )

        return text, None

    @staticmethod
    def validate_session_id(session_id: Any) -> Optional[Tuple]:
        from flask import jsonify

        if not isinstance(session_id, str) or not session_id.strip():
            return jsonify({"error": "Session ID required"}), 400

        if not SecurityConfig.SESSION_ID_PATTERN.fullmatch(session_id.strip()):
            return jsonify({"error": "Invalid session ID format"}), 400

        return None

    @staticmethod
    def validate_knowledge_field(
        key: str,
        value: Any,
        allowed_fields: set,
        max_field_length: int = SecurityConfig.MAX_FIELD_LENGTH,
    ) -> Optional[Tuple]:
        from flask import jsonify

        if key not in allowed_fields:
            return jsonify({"error": f"Unknown field: {key}"}), 400

        if not isinstance(value, str):
            return jsonify({"error": f"Field '{key}' must be a string"}), 400

        if len(value) > max_field_length:
            return jsonify({"error": f"Field '{key}' exceeds {max_field_length} characters"}), 400

        return None

    @staticmethod
    def validate_knowledge_data(
        data: Any,
        allowed_fields: set,
        max_field_length: int = SecurityConfig.MAX_FIELD_LENGTH,
    ) -> Optional[Tuple]:
        from flask import jsonify

        if not data or not isinstance(data, dict):
            return jsonify({"error": "No data provided"}), 400

        unknown = set(data.keys()) - allowed_fields
        if unknown:
            return jsonify({"error": f"Unknown fields: {', '.join(unknown)}"}), 400

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
    def parse_positive_int(raw: Any, maximum: int = 1000) -> int | None:
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
            settings.env_flag("TRUST_PROXY_HEADERS", SecurityConfig.TRUST_PROXY_HEADERS),
        )
        forwarded = request_obj.headers.get("X-Forwarded-For") if trust_proxy_headers else None
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request_obj.remote_addr or "unknown"


class SessionSecurityManager:
    """In-memory session store with automatic idle cleanup"""

    def __init__(
        self,
        max_sessions: int = SecurityConfig.MAX_SESSIONS,
        idle_minutes: int = SecurityConfig.SESSION_IDLE_MINUTES,
        cleanup_interval: int = SecurityConfig.CLEANUP_INTERVAL_SECONDS,
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

    _rate_limiter = RateLimiter(SecurityConfig.RATE_LIMITS)
    session_manager = SessionSecurityManager(
        max_sessions=SecurityConfig.MAX_SESSIONS,
        idle_minutes=SecurityConfig.SESSION_IDLE_MINUTES,
        cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
        manager_name="chat sessions",
    )
    return _rate_limiter, session_manager
