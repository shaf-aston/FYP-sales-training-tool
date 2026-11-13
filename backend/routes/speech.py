"""Replies read aloud, for both modes."""

from flask import Blueprint, Response, jsonify, request

from core.infra.constants import DICTATION
from core.infra.providers.dictation import NoSpeech, dictate
from core.infra.providers.speech import speak

from ..security import require_rate_limit

bp = Blueprint("speech", __name__, url_prefix="/api")


@bp.route("/speech", methods=["POST"])
@require_rate_limit("speech")
def speech():
    """Audio for the text in the speaker's voice ("seller", or "buyer" with the persona's name), or 204 so the
    browser uses its own voice."""
    data = request.get_json(silent=True) or {}
    try:
        speed = float(data.get("speed", 1.0))
    except (TypeError, ValueError):
        speed = 1.0
    audio = speak(str(data.get("text", ""))[:600], speaker=str(data.get("speaker", "seller")),
                  persona=str(data.get("persona", ""))[:80], hint=str(data.get("hint", ""))[:400], speed=speed)
    if not audio:
        return Response(status=204)
    return Response(audio, mimetype="audio/wav", headers={"Cache-Control": "private, max-age=86400"})


@bp.route("/dictate", methods=["POST"])
@require_rate_limit("dictate")
def dictate_route():
    """What the learner said: the recording as the body (or a form file "audio"), its text back; "" when nothing
    could be heard (a normal outcome, not an error: the mic picked up a cough, or the room)."""
    audio = request.files["audio"].read() if "audio" in request.files else request.get_data()
    if not audio:
        return jsonify({"error": "No audio was sent.", "code": "NO_AUDIO"}), 400
    if len(audio) > DICTATION["max_bytes"]:
        return jsonify({"error": "That recording is too long for one turn.", "code": "TOO_LONG"}), 413
    try:
        return jsonify({"success": True, "text": dictate(audio)})
    except NoSpeech:
        return jsonify({"success": True, "text": ""})
