"""Shared route helpers: session lookup, input validation and JSON shapes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any

from flask import current_app, jsonify, request

from core.constants import MAX_MESSAGE_LENGTH

from ..messages import MESSAGE_REQUIRED, SELL_SESSION_NOT_FOUND, SESSION_NOT_FOUND, UNSUPPORTED_PROVIDER
from ..security import InputValidator


@dataclass(frozen=True)
class Sessions:
    """The two live-session stores, kept once on ``app.extensions["sessions"]``.

    Named for the AI's side: ``seller`` holds buy mode's SellerBots, ``buyer`` holds
    sell mode's BuyerSessions.
    """

    seller: Any
    buyer: Any


_NOT_FOUND = {"seller": SESSION_NOT_FOUND, "buyer": SELL_SESSION_NOT_FOUND}


def require_session(kind: str):
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
        # The web app starts a new session when it sees this code.
        return None, (jsonify({"error": _NOT_FOUND[kind], "code": "SESSION_EXPIRED"}), 400)
    return found, None


def with_session(kind: str):
    """Route decorator: call the handler with the caller's live session, or return the lookup error."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            session, error = require_session(kind)
            if error:
                return error
            return view(session, *args, **kwargs)

        return wrapper

    return decorator


def history_json(history: list[dict]) -> list[dict]:
    """The transcript as the web app reads it: role and content only."""
    return [{"role": m["role"], "content": m["content"]} for m in history]


def validate_message(message_text):
    """Validate message text. Returns (clean_text, error_response)"""
    if not message_text or not isinstance(message_text, str):
        return None, (jsonify({"error": MESSAGE_REQUIRED}), 400)
    return InputValidator.validate_message(
        message_text.strip(),
        max_length=MAX_MESSAGE_LENGTH,
    )


def stage_fields(seller):
    """The buy-mode call's stage and strategy, as every buy response carries them."""
    call = seller.call
    return {"stage": call.current_stage.upper(), "strategy": call.strategy.upper()}


def validate_provider(data):
    """Return (provider, error). Error is a ready response when the provider is unknown."""
    from core.providers import list_providers

    provider = InputValidator.normalize_provider(data.get("provider"))
    supported = list_providers()
    if provider is not None and provider not in supported:
        return None, (
            jsonify(
                {
                    "error": UNSUPPORTED_PROVIDER,
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
