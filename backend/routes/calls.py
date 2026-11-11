"""Uploaded call endpoints (/api/calls): read a real call's transcript, and review it turn by turn.

Stateless: the transcript comes with every request and nothing is stored. Practising against the prospect goes
through /api/sell/init with the profile as `custom_buyer`. Unexpected failures fall through to the app's error
handler (logged, generic 500); an oversized body is a 413 before any route runs (limits.yaml max_request_bytes).
"""

from flask import Blueprint, jsonify, request

from core.calls.errors import CALL_TOO_LONG, CALL_TOO_SHORT, CALL_UNREADABLE, UNKNOWN_SPEAKER, CallError
from core.calls.reader import load_calls_config, read_call
from core.infra.loader import CONFIG_DIR
from core.sell_mode import sell_service
from core.sell_mode.sell_service import InvalidDifficulty

from ..messages import (
    CALL_TEXT_REQUIRED,
    CALL_TOO_LONG_TEXT,
    CALL_TOO_SHORT_TEXT,
    CALL_UNREADABLE_TEXT,
    CALL_UNKNOWN_SPEAKER_TEXT,
    INVALID_DIFFICULTY,
)
from ..security import require_rate_limit

bp = Blueprint("calls", __name__, url_prefix="/api/calls")

SAMPLE_FILE = "calls_sample.txt"   # in config/: the call behind "Try a sample call"
_ERRORS = {
    CALL_UNREADABLE: CALL_UNREADABLE_TEXT,
    CALL_TOO_LONG: CALL_TOO_LONG_TEXT,
    CALL_TOO_SHORT: CALL_TOO_SHORT_TEXT,
    UNKNOWN_SPEAKER: CALL_UNKNOWN_SPEAKER_TEXT,
}


def _read():
    """(reading, None), or (None, error response) for a missing transcript or one the reader refuses."""
    data = request.get_json(silent=True) or {}
    text, rep = data.get("text"), data.get("rep")
    if not isinstance(text, str) or not text.strip():
        return None, (jsonify({"error": CALL_TEXT_REQUIRED, "code": CALL_UNREADABLE}), 400)
    try:
        return read_call(text, rep if isinstance(rep, str) and rep.strip() else None), None
    except CallError as e:
        message = _ERRORS[e.code].format(max_chars=load_calls_config()["limits"]["max_chars"], name=e.detail)
        return None, (jsonify({"error": message, "code": e.code}), 400)


@bp.route("/sample", methods=["GET"])
def sample():
    """A realistic call transcript to try the feature without one of your own."""
    return jsonify({"success": True, "text": (CONFIG_DIR / SAMPLE_FILE).read_text("utf-8"), "filename": SAMPLE_FILE})


@bp.route("/read", methods=["POST"])
@require_rate_limit("calls")
def read():
    """Speakers, who the rep is, the turns, and the prospect's profile (see core/calls/reader.py)."""
    reading, error = _read()
    if error:
        return error
    return jsonify({"success": True, **reading.to_json()})


@bp.route("/review", methods=["POST"])
@require_rate_limit("calls")
def review():
    """The real call reviewed turn by turn: the rep's lines rated, as a practice session's review is.

    Replayed at the difficulty the learner picked (`difficulty`), else the one the profile read from the call.
    """
    reading, error = _read()
    if error:
        return error
    difficulty = (request.get_json(silent=True) or {}).get("difficulty") or reading.profile.difficulty
    try:
        return jsonify({"success": True, **sell_service.review_transcript(reading.history(), difficulty)})
    except InvalidDifficulty as e:
        return jsonify({"error": INVALID_DIFFICULTY.format(choices=", ".join(e.choices))}), 400
