"""Security module: Centralized security controls for Flask application.

Provides:
- Rate limiting (sliding window per IP + bucket)
- Prompt injection detection and sanitization
- Input validation (messages, knowledge fields)
- Response security headers
- Session lifecycle management with capacity limits
- Client IP extraction (proxy-aware)

Design Principle: All security logic isolated from business logic in app.py.
This module has NO dependencies on SalesChatbot, flow.py, content.py, or other
business logic modules. Security.py is purely defensive infrastructure.

Thread Safety: All components explicitly use locks (threading.Lock) for concurrent
request handling.
"""

import re
import time
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Tuple, Optional, Dict, Any, Callable

# Module-level logger for security events
logger = logging.getLogger(__name__)


# ─── Configuration ───────────────────────────────────────────────────────────

class SecurityConfig:
    """Centralized security configuration constants.

    All security thresholds and limits are defined here for easy tuning.
    """

    # Session management
    MAX_SESSIONS = 200  # Prevent memory exhaustion from bot spam
    SESSION_IDLE_MINUTES = 60
    CLEANUP_INTERVAL_SECONDS = 900  # 15 minutes

    # Message validation
    MAX_MESSAGE_LENGTH = 1000

    # Knowledge field validation — must match knowledge.MAX_FIELD_LENGTH in src/chatbot/knowledge.py
    MAX_FIELD_LENGTH = 1000

    # Rate limiting: (max_requests, window_seconds)
    RATE_LIMITS = {
        "init": (10, 60),   # 10 inits per 60 seconds
        "chat": (60, 60),   # 60 messages per 60 seconds
        "knowledge": (10, 60),  # 10 knowledge updates per 60 seconds
    }

    # Security headers
    SECURITY_HEADERS = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'X-XSS-Protection': '1; mode=block',
    }


# ─── Rate Limiting ───────────────────────────────────────────────────────────

class RateLimiter:
    """Thread-safe sliding window rate limiter.

    Tracks request timestamps per (IP, bucket) pair and enforces rate limits
    using a sliding window algorithm. Designed for Flask middleware use.

    Example:
        limiter = RateLimiter(SecurityConfig.RATE_LIMITS)
        if limiter.is_limited("192.168.1.1", "chat"):
            return error_response, 429
    """

    def __init__(self, limits: Dict[str, Tuple[int, int]]):
        """Initialize rate limiter.

        Args:
            limits: dict mapping bucket name to (max_requests, window_seconds)
        """
        self.limits = limits
        self._store: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_limited(self, ip: str, bucket: str) -> bool:
        """Check if (ip, bucket) has exceeded rate limit.

        Uses sliding window: removes old timestamps outside window, checks count,
        appends current timestamp.

        Args:
            ip: Client IP address
            bucket: Rate limit bucket ("init", "chat", etc.)

        Returns:
            True if limit exceeded, False otherwise
        """
        max_req, window = self.limits[bucket]
        key = f"{bucket}:{ip}"
        now = time.time()

        with self._lock:
            dq = self._store[key]
            # Remove expired timestamps
            while dq and now - dq[0] > window:
                dq.popleft()

            # Check if limit exceeded
            if len(dq) >= max_req:
                return True

            # Record this request
            dq.append(now)
            return False


def require_rate_limit(bucket: str) -> Callable:
    """Flask route decorator: Apply rate limiting.

    Extracts client IP, checks rate limit, returns 429 if exceeded.
    Otherwise allows request to proceed.

    Usage:
        @app.route('/api/chat', methods=['POST'])
        @require_rate_limit('chat')
        def chat():
            # Rate limit already checked
            pass

    Args:
        bucket: Rate limit bucket name

    Returns:
        Decorator function
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Note: request must be imported in app.py where this is used
            from flask import request, jsonify

            ip = ClientIPExtractor.get_ip(request)
            if rate_limiter is not None and rate_limiter.is_limited(ip, bucket):
                return jsonify({
                    "error": "Too many requests. Please slow down."
                }), 429

            return f(*args, **kwargs)
        return wrapper
    return decorator


# Global rate limiter instance (initialized after class definition)
rate_limiter: Optional[RateLimiter] = None


# ─── Prompt Injection Detection ──────────────────────────────────────────────

class PromptInjectionValidator:
    """Detects and sanitizes prompt injection attacks.

    Uses regex patterns to detect common jailbreak attempts:
    - "Ignore previous instructions"
    - "Disregard X"
    - "Forget everything"
    - "Print your prompt"
    - "Your real instructions"
    - "Act as if you..."

    Defence-in-depth: This is the second line of defence (first is Constitutional
    AI system prompt). Catches obvious patterns before they reach the LLM.
    """

    # Regex pattern for common injection attempts
    INJECTION_PATTERN = re.compile(
        r'\bignore\s+(all\s+)?(previous|prior|above)\s+instructions?\b'
        r'|\bdisregard\s+.{0,30}instructions?\b'
        r'|\bforget\s+(everything|all|your\s+(previous|prior|above|system))\b'
        r'|\bprint\s+(your\s+)?(system\s+)?prompt\b'
        r'|\byour\s+real\s+instructions?\b'
        r'|\bact\s+as\s+(if\s+you\s+(are|were)|a\b)',
        re.IGNORECASE,
    )

    @staticmethod
    def sanitize(text: str, log_fn: Optional[Callable] = None) -> str:
        """Sanitize user input by stripping injection patterns.

        Replaces matched patterns with '[removed]' placeholder. This allows
        the conversation to continue naturally rather than hard-failing,
        which would inform the attacker that the filter triggered.

        Args:
            text: User input text
            log_fn: Optional logging function (e.g., logger.warning)

        Returns:
            Sanitized text (original if no matches)
        """
        sanitized = PromptInjectionValidator.INJECTION_PATTERN.sub('[removed]', text)
        if sanitized != text and log_fn:
            log_fn("Prompt injection stripped from message")
        return sanitized

    @staticmethod
    def contains_injection(text: str) -> bool:
        """Check if text contains injection patterns without sanitizing.

        Args:
            text: User input text

        Returns:
            True if injection pattern detected, False otherwise
        """
        return bool(PromptInjectionValidator.INJECTION_PATTERN.search(text))


# ─── Response Security Headers ───────────────────────────────────────────────

class SecurityHeadersMiddleware:
    """Flask after_request middleware for security headers.

    Applies standard security headers to every response:
    - X-Frame-Options: Prevents clickjacking
    - X-Content-Type-Options: Prevents MIME sniffing
    - Referrer-Policy: Limits referrer leakage
    - X-XSS-Protection: Legacy XSS filter hint

    Usage:
        app.after_request(SecurityHeadersMiddleware.apply)
    """

    @staticmethod
    def apply(response):
        """Add security headers to response.

        Args:
            response: Flask response object

        Returns:
            Modified response with security headers
        """
        for key, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[key] = value
        return response


# ─── Input Validation ───────────────────────────────────────────────────────

class InputValidator:
    """General-purpose input validation utilities.

    Validates:
    - Chat messages (non-empty, within length bounds)
    - Knowledge fields (type checking, length limits)
    """

    @staticmethod
    def validate_message(
        text: str,
        injection_validator: PromptInjectionValidator,
        max_length: int = SecurityConfig.MAX_MESSAGE_LENGTH
    ) -> Tuple[Optional[str], Optional[Tuple]]:
        """Validate chat message.

        Sanitizes injection patterns, checks for empty input, enforces length limit.

        Args:
            text: User message
            injection_validator: PromptInjectionValidator instance
            max_length: Maximum message length in characters

        Returns:
            Tuple of (clean_text, error_response)
            - If valid: (clean_text, None)
            - If invalid: (None, (error_json, status_code))
        """
        from flask import jsonify

        # Sanitize injection patterns
        text = injection_validator.sanitize(text.strip())

        # Check for empty message
        if not text:
            return None, (jsonify({"error": "Message required"}), 400)

        # Check length
        if len(text) > max_length:
            return None, (
                jsonify({
                    "error": f"Message too long (max {max_length} characters)"
                }),
                400
            )

        return text, None

    @staticmethod
    def validate_knowledge_field(
        key: str,
        value: Any,
        allowed_fields: set,
        max_field_length: int = SecurityConfig.MAX_FIELD_LENGTH
    ) -> Optional[Tuple]:
        """Validate a single knowledge field.

        Checks:
        - Field is in allowed list
        - Value is a string
        - Value within length limit

        Args:
            key: Field name
            value: Field value
            allowed_fields: Set of allowed field names
            max_field_length: Maximum field value length

        Returns:
            None if valid, (error_json, status_code) if invalid
        """
        from flask import jsonify

        # Check field is allowed (defence-in-depth; also checked in knowledge.py)
        if key not in allowed_fields:
            return jsonify({"error": f"Unknown field: {key}"}), 400

        # Check type
        if not isinstance(value, str):
            return jsonify({
                "error": f"Field '{key}' must be a string"
            }), 400

        # Check length
        if len(value) > max_field_length:
            return jsonify({
                "error": f"Field '{key}' exceeds {max_field_length} characters"
            }), 400

        return None

    @staticmethod
    def validate_knowledge_data(
        data: Any,
        allowed_fields: set,
        max_field_length: int = SecurityConfig.MAX_FIELD_LENGTH
    ) -> Optional[Tuple]:
        """Validate entire knowledge update payload.

        Args:
            data: Request JSON data
            allowed_fields: Set of allowed field names
            max_field_length: Maximum field value length

        Returns:
            None if valid, (error_json, status_code) if invalid
        """
        from flask import jsonify

        # Check data is dict
        if not data or not isinstance(data, dict):
            return jsonify({"error": "No data provided"}), 400

        # Check for unknown fields
        unknown = set(data.keys()) - allowed_fields
        if unknown:
            return jsonify({
                "error": f"Unknown fields: {', '.join(unknown)}"
            }), 400

        # Validate each field
        for key, value in data.items():
            error = InputValidator.validate_knowledge_field(
                key, value, allowed_fields, max_field_length
            )
            if error:
                return error

        return None


# ─── Client IP Extraction ───────────────────────────────────────────────────

class ClientIPExtractor:
    """Extract client IP from Flask request, handling proxy scenarios.

    In production (Render, AWS, etc.), requests come through proxies that
    set X-Forwarded-For header. Falls back to request.remote_addr for
    direct connections or localhost testing.
    """

    @staticmethod
    def get_ip(request_obj) -> str:
        """Extract client IP from Flask request.

        Priority:
        1. X-Forwarded-For header (first IP if comma-separated)
        2. request.remote_addr (direct connection)
        3. 'unknown' (fallback if both missing)

        Args:
            request_obj: Flask request object

        Returns:
            Client IP address string
        """
        forwarded = request_obj.headers.get('X-Forwarded-For')
        if forwarded:
            # X-Forwarded-For can be comma-separated list; take first
            return forwarded.split(',')[0].strip()
        return request_obj.remote_addr or 'unknown'


# ─── Session Management ──────────────────────────────────────────────────────

class SessionSecurityManager:
    """Thread-safe session lifecycle management.

    Manages in-memory session storage with:
    - Capacity ceiling (prevents memory exhaustion)
    - Idle timeout enforcement (background cleanup)
    - Thread-safe access with locks

    Session Entry Format:
        {
            "bot": SalesChatbot,  # The chatbot instance
            "ts": datetime        # Last access timestamp
        }
    """

    def __init__(
        self,
        max_sessions: int = SecurityConfig.MAX_SESSIONS,
        idle_minutes: int = SecurityConfig.SESSION_IDLE_MINUTES,
        cleanup_interval: int = SecurityConfig.CLEANUP_INTERVAL_SECONDS,
    ):
        """Initialize session manager.

        Args:
            max_sessions: Maximum concurrent sessions before rejecting new ones
            idle_minutes: Session idle timeout in minutes
            cleanup_interval: Background cleanup interval in seconds
        """
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.idle_minutes = idle_minutes
        self.cleanup_interval = cleanup_interval

    def get(self, session_id: str) -> Optional[Any]:
        """Retrieve session and update timestamp.

        Args:
            session_id: Session identifier

        Returns:
            Chatbot instance if found, None otherwise
        """
        with self._lock:
            entry = self._sessions.get(session_id)
            if entry:
                # Update access timestamp (used for idle detection)
                entry["ts"] = datetime.now()
                return entry["bot"]
        return None

    def set(self, session_id: str, chatbot: Any) -> None:
        """Store session (new or update).

        Args:
            session_id: Session identifier
            chatbot: SalesChatbot instance
        """
        with self._lock:
            self._sessions[session_id] = {
                "bot": chatbot,
                "ts": datetime.now()
            }

    def delete(self, session_id: str) -> None:
        """Remove session immediately.

        Args:
            session_id: Session identifier
        """
        with self._lock:
            self._sessions.pop(session_id, None)

    def can_create(self) -> bool:
        """Check if new session can be created (capacity check).

        Returns:
            True if under capacity, False if at ceiling
        """
        with self._lock:
            return len(self._sessions) < self.max_sessions

    def count(self) -> int:
        """Get current session count.

        Returns:
            Number of active sessions
        """
        with self._lock:
            return len(self._sessions)

    def cleanup_expired(self) -> int:
        """Remove sessions idle > idle_minutes.

        Returns:
            Number of sessions cleaned up
        """
        with self._lock:
            now = datetime.now()
            max_idle = timedelta(minutes=self.idle_minutes)

            expired_ids = [
                sid for sid, s in self._sessions.items()
                if now - s["ts"] > max_idle
            ]

            for sid in expired_ids:
                del self._sessions[sid]

            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} idle sessions")

            return len(expired_ids)

    def start_background_cleanup(self) -> None:
        """Start background cleanup thread (daemon mode).

        Periodically removes idle sessions. Runs in daemon mode
        so doesn't prevent application shutdown.
        """
        def cleanup_loop():
            while True:
                try:
                    time.sleep(self.cleanup_interval)
                    self.cleanup_expired()
                except Exception as e:
                    logger.error(f"Cleanup thread error: {e}")

        thread = threading.Thread(target=cleanup_loop, daemon=True)
        thread.start()
        logger.info(
            f"Started background cleanup thread "
            f"(interval: {self.cleanup_interval}s)"
        )


# ─── Module Initialization ───────────────────────────────────────────────────

def initialize_security(
    app_logger=None,
) -> Tuple[RateLimiter, SessionSecurityManager, PromptInjectionValidator]:
    """Initialize security module.

    Creates singleton instances of security components. Should be called once
    during Flask app startup.

    Args:
        app_logger: Flask app logger (for security events)

    Returns:
        Tuple of (rate_limiter, session_manager, injection_validator)
    """
    global rate_limiter

    if app_logger:
        logger.handlers = app_logger.handlers
        logger.setLevel(app_logger.level)

    rate_limiter = RateLimiter(SecurityConfig.RATE_LIMITS)
    session_manager = SessionSecurityManager(
        max_sessions=SecurityConfig.MAX_SESSIONS,
        idle_minutes=SecurityConfig.SESSION_IDLE_MINUTES,
        cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
    )
    injection_validator = PromptInjectionValidator()

    return rate_limiter, session_manager, injection_validator
