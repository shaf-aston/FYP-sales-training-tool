"""Shared route-layer helpers: session lookup, provider validation, serialization."""

from __future__ import annotations

from functools import wraps

from flask import jsonify, request

from ..messages import SESSION_NOT_FOUND
from ..security import InputValidator


def make_require_session(get_session, not_found_message=SESSION_NOT_FOUND):
    """Build the one session-lookup seam.

    ``get_session`` takes a session id and returns the live object or None. Every
    route that needs a session uses the result of this factory, so the validation,
    the error body, the error code and the status code are defined in one place.
    """

    def require_session():
        session_id = request.headers.get("X-Session-ID")
        session_error = InputValidator.validate_session_id(session_id)
        if session_error:
            return None, session_error

        found = get_session(session_id)
        if not found:
            from flask import current_app

            current_app.logger.warning(
                "Session not found for %s (id=%s...)", request.path, str(session_id)[:8]
            )
            return None, (
                jsonify({"error": not_found_message, "code": "SESSION_EXPIRED"}),
                400,
            )
        return found, None

    return require_session


def with_session(bp):
    """Route decorator: pass the session object to the handler, or return the error."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            session_bot, error = bp.require_session()
            if error:
                return error
            return view(session_bot, *args, **kwargs)

        return wrapper

    return decorator


def validate_provider(data):
    """Return (provider, error). Error is a ready response when the provider is unknown."""
    from core.providers import list_providers

    provider = InputValidator.normalize_provider(data.get("provider"))
    supported = list_providers()
    if provider is not None and provider not in supported:
        return None, (
            jsonify(
                {
                    "error": "Unsupported provider",
                    "code": "UNSUPPORTED_PROVIDER",
                    "supported_providers": supported,
                }
            ),
            400,
        )
    return provider, None


def safe_latency_ms(value) -> float | None:
    """Round latency values for JSON responses without crashing on None."""
    if value is None:
        return None
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None
