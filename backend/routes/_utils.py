"""Shared route-layer helpers: session lookup, provider validation, serialization."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any

from flask import current_app, jsonify, request

from core.constants import MAX_MESSAGE_LENGTH

from ..messages import MESSAGE_REQUIRED, SESSION_NOT_FOUND
from ..security import InputValidator


@dataclass(frozen=True)
class Sessions:
    """The two live-session registries, stored once on ``app.extensions["sessions"]``.

    Named for the AI's side: ``seller`` holds buy mode's SellerBots, ``buyer`` holds
    sell mode's BuyerSessions.
    """

    seller: Any
    buyer: Any


def require_session(kind="seller", not_found_message=SESSION_NOT_FOUND):
    """Look up the caller's live session: returns (session, None) or (None, error response).

    ``kind`` is "seller" (buy mode) or "buyer" (sell mode). Validation, error body, code and status live here only.
    """
    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return None, session_error

    found = getattr(current_app.extensions["sessions"], kind).get(session_id)
    if not found:
        current_app.logger.warning(
            "Session not found for %s (id=%s...)", request.path, str(session_id)[:8]
        )
        return None, (
            jsonify({"error": not_found_message, "code": "SESSION_EXPIRED"}),
            400,
        )
    return found, None


def with_session(view):
    """Route decorator: pass the session object to the handler, or return the error."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        session_bot, error = require_session()
        if error:
            return error
        return view(session_bot, *args, **kwargs)

    return wrapper


def validate_message(message_text):
    """Validate message text. Returns (clean_text, error_response)"""
    if not message_text or not isinstance(message_text, str):
        return None, (jsonify({"error": MESSAGE_REQUIRED}), 400)
    return InputValidator.validate_message(
        message_text.strip(),
        max_length=MAX_MESSAGE_LENGTH,
    )


def bot_state(session_bot):
    """Common stage/strategy fields for JSON responses"""
    flow = session_bot.flow_engine
    return {"stage": flow.current_stage.upper(), "strategy": flow.flow_type.upper()}


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
