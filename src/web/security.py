"""Rate limiting, input validation, and session management"""

import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from chatbot.constants import MAX_FIELD_LENGTH as CHATBOT_MAX_FIELD_LENGTH
from web.messages import RATE_LIMIT_ERROR

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security thresholds and limits in one place"""

    # Session management
    MAX_SESSIONS = 200  # Prevent memory exhaustion from bot spam
    SESSION_IDLE_MINUTES = 60
    CLEANUP_INTERVAL_SECONDS = 900  # 15 minutes

    # Message validation
    MAX_MESSAGE_LENGTH = 1000

    # Knowledge field validation — must match knowledge.MAX_FIELD_LENGTH in src/chatbot/knowledge.py
    # Use canonical value from chatbot.constants to avoid divergence
    MAX_FIELD_LENGTH = CHATBOT_MAX_FIELD_LENGTH

    # Rate limiting: (max_requests, window_seconds)
    RATE_LIMITS = {
        "init": (10, 60),  # 10 inits per 60 seconds
        "chat": (60, 60),  # 60 messages per 60 seconds
        "knowledge": (10, 60),  # 10 knowledge updates per 60 seconds
    }

    # Security headers
    SECURITY_HEADERS = {
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-XSS-Protection": "1; mode=block",
    }


class RateLimiter:
    """tracks request counts per IP/bucket"""

    def __init__(self, limits: Dict[str, Tuple[int, int]]):
        self.limits = limits
        self._store: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_limited(self, ip: str, bucket: str) -> bool:
        """check if this IP is over the limit"""
        max_req, window = self.limits[bucket]
        key = f"{bucket}:{ip}"
        now = time.time()

        with self._lock:
            dq = self._store[key]
            while dq and now - dq[0] > window:
                dq.popleft()

            if len(dq) >= max_req:
                return True

            dq.append(now)
            return False


def require_rate_limit(bucket: str) -> Callable:
    """rate-limit decorator by client IP"""

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


# Global rate limiter instance (initialized after class definition)
_rate_limiter: Optional[RateLimiter] = None


# Privileged mutation guard decorator
def require_privileged_mutation(f: Callable) -> Callable:
    """Decorator to optionally require an admin token for sensitive mutations

    Controlled by config/env var `REQUIRE_ADMIN_FOR_STAGE_MUTATION`
    When enabled, the request must include header `X-Admin-Token` or
    `Authorization: Bearer <token>` matching `ADMIN_TOKEN` (env or app config)
    The check is bypassed when Flask `TESTING` is true to keep tests deterministic
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        from flask import current_app, jsonify, request

        # Feature flag: prefer explicit app config, otherwise check env var
        env_flag = (
            os.environ.get("REQUIRE_ADMIN_FOR_STAGE_MUTATION", "").lower() == "true"
        )
        require_admin = current_app.config.get(
            "REQUIRE_ADMIN_FOR_STAGE_MUTATION", env_flag
        )

        # If not enabled, no-op
        if not require_admin:
            return f(*args, **kwargs)

        # Allow tests to run without admin token
        if current_app.config.get("TESTING"):
            return f(*args, **kwargs)

        token_header = request.headers.get("X-Admin-Token") or request.headers.get(
            "Authorization"
        )
        admin_token = os.environ.get("ADMIN_TOKEN") or current_app.config.get(
            "ADMIN_TOKEN"
        )

        if not admin_token or not token_header:
            return jsonify({"error": "Admin token required"}), 403

        token = token_header
        if isinstance(token, str) and token.lower().startswith("bearer "):
            token = token.split(None, 1)[1]

        if token != admin_token:
            return jsonify({"error": "Invalid admin token"}), 403

        return f(*args, **kwargs)

    return wrapper


class PromptInjectionValidator:
    """strips obvious prompt injection patterns"""

    # Regex pattern for common injection attempts
    INJECTION_PATTERN = re.compile(
        r"\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b"
        r"|\bdisregard\s+.{0,30}instructions?\b"
        r"|\bforget\s+(everything|all|your\s+(previous|prior|above|system))\b"
        r"|\bprint\s+(your\s+)?(system\s+)?prompt\b"
        r"|\byour\s+real\s+instructions?\b"
        r"|\bact\s+as\s+(if\s+you\s+(are|were)|a\b)",
        re.IGNORECASE,
    )

    @staticmethod
    def sanitize(text: str, log_fn: Optional[Callable] = None) -> str:
        """swap injection matches for [removed]"""
        sanitized = PromptInjectionValidator.INJECTION_PATTERN.sub("[removed]", text)
        if sanitized != text and log_fn:
            log_fn("Prompt injection stripped from message")
        return sanitized

    @staticmethod
    def contains_injection(text: str) -> bool:
        """True if the text has injection patterns (no mutation)"""
        return bool(PromptInjectionValidator.INJECTION_PATTERN.search(text))


class SecurityHeadersMiddleware:
    """bolts security headers onto responses"""

    @staticmethod
    def apply(response):
        """Attach headers and return response"""
        for key, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[key] = value
        return response


class InputValidator:
    """Message and knowledge field validation"""

    @staticmethod
    def validate_message(
        text: str,
        injection_validator: PromptInjectionValidator,
        max_length: int = SecurityConfig.MAX_MESSAGE_LENGTH,
    ) -> Tuple[Optional[str], Optional[Tuple]]:
        """clean and length-check a message"""
        from flask import jsonify

        # Sanitize injection patterns
        text = injection_validator.sanitize(text.strip())

        # Check for empty message
        if not text:
            return None, (jsonify({"error": "Message required"}), 400)

        # Check length
        if len(text) > max_length:
            return None, (
                jsonify({"error": f"Message too long (max {max_length} characters)"}),
                400,
            )

        return text, None

    @staticmethod
    def validate_knowledge_field(
        key: str,
        value: Any,
        allowed_fields: set,
        max_field_length: int = SecurityConfig.MAX_FIELD_LENGTH,
    ) -> Optional[Tuple]:
        """validate one knowledge field"""
        from flask import jsonify

        # Check field is allowed (defence-in-depth; also checked in knowledge.py)
        if key not in allowed_fields:
            return jsonify({"error": f"Unknown field: {key}"}), 400

        # Check type
        if not isinstance(value, str):
            return jsonify({"error": f"Field '{key}' must be a string"}), 400

        # Check length
        if len(value) > max_field_length:
            return jsonify(
                {"error": f"Field '{key}' exceeds {max_field_length} characters"}
            ), 400

        return None

    @staticmethod
    def validate_knowledge_data(
        data: Any,
        allowed_fields: set,
        max_field_length: int = SecurityConfig.MAX_FIELD_LENGTH,
    ) -> Optional[Tuple]:
        """validate all knowledge fields at once"""
        from flask import jsonify

        # Check data is dict
        if not data or not isinstance(data, dict):
            return jsonify({"error": "No data provided"}), 400

        # Check for unknown fields
        unknown = set(data.keys()) - allowed_fields
        if unknown:
            return jsonify({"error": f"Unknown fields: {', '.join(unknown)}"}), 400

        # Validate each field
        for key, value in data.items():
            error = InputValidator.validate_knowledge_field(
                key, value, allowed_fields, max_field_length
            )
            if error:
                return error

        return None


class ClientIPExtractor:
    """grabs the real client IP"""

    @staticmethod
    def get_ip(request_obj) -> str:
        """X-Forwarded-For if present, else remote_addr"""
        forwarded = request_obj.headers.get("X-Forwarded-For")
        if forwarded:
            # X-Forwarded-For can be comma-separated list; take first
            return forwarded.split(",")[0].strip()
        return request_obj.remote_addr or "unknown"


class SessionSecurityManager:
    """in-memory session store with idle cleanup"""

    def __init__(
        self,
        max_sessions: int = SecurityConfig.MAX_SESSIONS,
        idle_minutes: int = SecurityConfig.SESSION_IDLE_MINUTES,
        cleanup_interval: int = SecurityConfig.CLEANUP_INTERVAL_SECONDS,
    ):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.idle_minutes = idle_minutes
        self.cleanup_interval = cleanup_interval

    def get(self, session_id: str) -> Optional[Any]:
        """fetch bot and bump its last-seen time"""
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry:
                # Update access timestamp (used for idle detection)
                entry["ts"] = datetime.now()
                return entry["bot"]
        return None

    def set(self, session_id: str, chatbot: Any) -> None:
        """Store or overwrite a session"""
        with self._lock:
            self._sessions[session_id] = {"bot": chatbot, "ts": datetime.now()}

    def delete(self, session_id: str) -> None:
        """Drop a session immediately"""
        with self._lock:
            self._sessions.pop(session_id, None)

    def can_create(self) -> bool:
        """True if we're under the session cap"""
        with self._lock:
            return len(self._sessions) < self.max_sessions

    def count(self) -> int:
        """Current number of active sessions"""
        with self._lock:
            return len(self._sessions)

    def _cleanup_expired(self) -> int:
        """Delete idle sessions. Returns count of sessions removed"""
        with self._lock:
            now = datetime.now()
            max_idle = timedelta(minutes=self.idle_minutes)

            expired_ids = [
                sid for sid, s in self._sessions.items() if now - s["ts"] > max_idle
            ]

            for sid in expired_ids:
                del self._sessions[sid]

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} idle sessions")

            return len(expired_ids)

    def start_background_cleanup(self) -> None:
        """start the cleanup daemon"""

        def cleanup_loop():
            while True:
                try:
                    time.sleep(self.cleanup_interval)
                    self._cleanup_expired()
                except Exception as e:
                    logger.error(f"Cleanup thread error: {e}")

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logger.info(
            f"Started background cleanup thread (interval: {self.cleanup_interval}s)"
        )


def initialize_security(
    app_logger=None,
) -> Tuple[RateLimiter, SessionSecurityManager, PromptInjectionValidator]:
    """init security singletons (call once at startup)"""
    global _rate_limiter

    if app_logger:
        logger.handlers = app_logger.handlers
        logger.setLevel(app_logger.level)

    _rate_limiter = RateLimiter(SecurityConfig.RATE_LIMITS)
    session_manager = SessionSecurityManager(
        max_sessions=SecurityConfig.MAX_SESSIONS,
        idle_minutes=SecurityConfig.SESSION_IDLE_MINUTES,
        cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
    )
    injection_validator = PromptInjectionValidator()

    return _rate_limiter, session_manager, injection_validator
