"""Rate limiting, input validation and session management"""

import hmac
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from core.constants import MAX_FIELD_LENGTH as CHATBOT_MAX_FIELD_LENGTH
from .messages import RATE_LIMIT_ERROR

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security thresholds and limits in one place"""

    SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")

    # Session management
    MAX_SESSIONS = 200  # Prevent memory exhaustion from bot spam
    SESSION_IDLE_MINUTES = 60
    CLEANUP_INTERVAL_SECONDS = 900  # 15 minutes
    TRUST_PROXY_HEADERS = False

    # Message validation
    MAX_MESSAGE_LENGTH = 1000

    # Knowledge field validation - must match knowledge.MAX_FIELD_LENGTH in src/chatbot/knowledge.py
    # Use canonical value from chatbot.constants to avoid divergence
    MAX_FIELD_LENGTH = CHATBOT_MAX_FIELD_LENGTH

    # Rate limiting: (max_requests, window_seconds)
    RATE_LIMITS = {
        "init": (10, 60),  # 10 inits per 60 seconds
        "chat": (60, 60),  # 60 messages per 60 seconds
        "knowledge": (10, 60),  # 10 knowledge updates per 60 seconds
        "prospect": (30, 60),  # Prospect mode is more expensive than plain reads
        "feedback": (5, 300),  # Keep append-only feedback from becoming a spam sink
    }

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
    def _config_flag(config_obj, name: str, default: bool = False) -> bool:
        if config_obj is not None and name in config_obj:
            value = config_obj.get(name)
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            if value is not None:
                return bool(value)
        return _env_flag(name, default)

    @classmethod
    def require_admin_for_stage_mutation(cls, config_obj=None) -> bool:
        return cls._config_flag(
            config_obj,
            "REQUIRE_ADMIN_FOR_STAGE_MUTATION",
            # Keep stage jumping available in local/dev unless explicitly locked down.
            default=False,
        )

    @classmethod
    def content_security_policy(cls, config_obj=None) -> str:
        script_src = ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]
        media_src = ["'self'", "data:", "blob:"]
        connect_src = ["'self'"]

        return (
            "default-src 'self'; "
            f"script-src {' '.join(script_src)}; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            f"media-src {' '.join(media_src)}; "
            f"connect-src {' '.join(connect_src)}; "
            "font-src 'self' data:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )


def _env_flag(name: str, default: bool = False) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class RateLimiter:
    """Track request counts per IP/bucket"""

    def __init__(self, limits: Dict[str, Tuple[int, int]]):
        self.limits = limits
        self._store: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_limited(self, ip: str, bucket: str) -> bool:
        """Check if this IP is over the limit"""
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


# Global rate limiter instance (initialized after class definition)
_rate_limiter: Optional[RateLimiter] = None


# Privileged mutation guard decorator
def require_privileged_mutation(f: Callable) -> Callable:
    """Decorator to optionally require an admin token for sensitive mutations

    Controlled by config/env var `REQUIRE_ADMIN_FOR_STAGE_MUTATION`
    When enabled, the request must include header `X-Admin-Token` or
    `Authorization: Bearer <token>` matching `ADMIN_TOKEN` (env or app config)
    Defaults to enabled. The check is bypassed when Flask `TESTING` is true
    to keep tests deterministic.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        from flask import current_app, jsonify, request

        # Feature flag: prefer explicit app config, otherwise check env var
        require_admin = SecurityConfig.require_admin_for_stage_mutation(
            current_app.config
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
        admin_token = os.environ.get("ADMIN_TOKEN") or current_app.config.get("ADMIN_TOKEN")

        if not admin_token or not token_header:
            logger.warning(
                "Blocked privileged mutation without admin token path=%s ip=%s",
                request.path,
                ClientIPExtractor.get_ip(request),
            )
            return jsonify({"error": "Admin token required"}), 403

        if not has_valid_admin_token(request, current_app.config):
            logger.warning(
                "Blocked privileged mutation with invalid admin token path=%s ip=%s",
                request.path,
                ClientIPExtractor.get_ip(request),
            )
            return jsonify({"error": "Invalid admin token"}), 403

        return f(*args, **kwargs)

    return wrapper


def require_strict_admin_token(f: Callable) -> Callable:
    """Decorator for endpoints that should never be public."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        from flask import current_app, jsonify, request

        if current_app.config.get("TESTING"):
            return f(*args, **kwargs)

        admin_token = os.environ.get("ADMIN_TOKEN") or current_app.config.get("ADMIN_TOKEN")
        if not admin_token:
            logger.error("Strict admin route %s accessed without ADMIN_TOKEN configured", request.path)
            return jsonify({"error": "Admin access unavailable"}), 503

        if not has_valid_admin_token(request, current_app.config):
            logger.warning(
                "Blocked strict admin route without valid token path=%s ip=%s",
                request.path,
                ClientIPExtractor.get_ip(request),
            )
            return jsonify({"error": "Admin token required"}), 403

        return f(*args, **kwargs)

    return wrapper


def _extract_supplied_admin_token(request_obj) -> str:
    token = request_obj.headers.get("X-Admin-Token") or request_obj.headers.get(
        "Authorization", ""
    )
    if isinstance(token, str) and token.lower().startswith("bearer "):
        return token.split(None, 1)[1]
    return token or ""


def has_valid_admin_token(request_obj, config_obj) -> bool:
    admin_token = os.environ.get("ADMIN_TOKEN") or config_obj.get("ADMIN_TOKEN")
    supplied_token = _extract_supplied_admin_token(request_obj)
    if not admin_token or not supplied_token:
        return False
    return hmac.compare_digest(str(supplied_token), str(admin_token))


class PromptInjectionValidator:
    """Strip obvious prompt injection patterns"""

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
        """Swap injection matches for [removed]"""
        sanitized = PromptInjectionValidator.INJECTION_PATTERN.sub("[removed]", text)
        if sanitized != text and log_fn:
            log_fn("Prompt injection stripped from message")
        return sanitized

    @staticmethod
    def contains_injection(text: str) -> bool:
        """Return True if the text has injection patterns (no mutation)"""
        return bool(PromptInjectionValidator.INJECTION_PATTERN.search(text))


class SecurityHeadersMiddleware:
    """Attach security headers to Flask responses"""

    @staticmethod
    def apply(response):
        """Attach headers and return response"""
        from flask import current_app, request

        for key, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[key] = value
        response.headers["Content-Security-Policy"] = SecurityConfig.content_security_policy(
            current_app.config
        )
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


class InputValidator:
    """Message and knowledge field validation"""

    @staticmethod
    def validate_message(
        text: str,
        injection_validator: PromptInjectionValidator,
        max_length: int = SecurityConfig.MAX_MESSAGE_LENGTH,
    ) -> Tuple[Optional[str], Optional[Tuple]]:
        """Clean and length-check a message"""
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
    def validate_session_id(session_id: Any) -> Optional[Tuple]:
        """Reject malformed session identifiers early."""
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
        """Validate one knowledge field"""
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
        """Validate all knowledge fields at once"""
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

    @staticmethod
    def normalize_provider(raw: Any) -> str | None:
        """Return None for non-string, empty, or auto-sentinel provider values."""
        if not isinstance(raw, str):
            return None
        v = raw.strip().lower()
        return None if (not v or v == "auto") else v


class ClientIPExtractor:
    """Extract the real client IP address"""

    @staticmethod
    def get_ip(request_obj) -> str:
        """X-Forwarded-For if present, else remote_addr"""
        from flask import current_app

        trust_proxy_headers = current_app.config.get(
            "TRUST_PROXY_HEADERS",
            _env_flag("TRUST_PROXY_HEADERS", SecurityConfig.TRUST_PROXY_HEADERS),
        )
        forwarded = request_obj.headers.get("X-Forwarded-For") if trust_proxy_headers else None
        if forwarded:
            # X-Forwarded-For can be comma-separated list; take first
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
        """Fetch bot and update its last-seen timestamp"""
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
        """Start the cleanup daemon thread"""
        with self._lock:
            if self._cleanup_started:
                logger.debug(
                    "Background cleanup thread already running for %s",
                    self.manager_name,
                )
                return
            self._cleanup_started = True

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
            "Started background cleanup thread for %s (interval: %ss)",
            self.manager_name,
            self.cleanup_interval,
        )


def initialize_security(
    app_logger=None,
) -> Tuple[RateLimiter, SessionSecurityManager, PromptInjectionValidator]:
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
    injection_validator = PromptInjectionValidator()

    return _rate_limiter, session_manager, injection_validator
