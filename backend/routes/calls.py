"""Uploaded call endpoints (/api/calls): turn a recording into a transcript, read a real call's transcript, and
review it turn by turn.

Stateless: the transcript (or recording) comes with every request and nothing is stored. Practising against the prospect goes
through /api/sell/init with the profile as `custom_buyer`. Unexpected failures fall through to the app's error
handler (logged, generic 500); an oversized body is a 413 before any route runs (limits.yaml max_request_bytes).
"""

from flask import Blueprint, jsonify, request

from core.calls.errors import CALL_ONE_SPEAKER, CALL_TOO_LONG, CALL_TOO_SHORT, CALL_UNREADABLE, UNKNOWN_SPEAKER, CallError
from core.calls.audio import as_transcript, label_speakers
from core.calls.audio_parts import AudioUnreadable, can_split, transcribe_in_parts
from core.calls.reader import load_calls_config, read_call
from core.infra.constants import CALL_LIMITS, LLM, MAX_REQUEST_BYTES, TRANSCRIPTION
from core.infra.providers.router import ProviderRouter, ProviderUnavailable, complete
from core.infra.providers.transcribe import TranscriptionUnavailable, transcribe
from core.infra.loader import CONFIG_DIR
from core.sell_mode import sell_service
from core.infra.utils import file_ext
from core.sell_mode.sell_service import InvalidDifficulty

from ..messages import (
    CALL_ONE_SPEAKER_TEXT,
    CALL_TEXT_REQUIRED,
    CALL_TOO_LONG_TEXT,
    CALL_TOO_SHORT_TEXT,
    CALL_UNREADABLE_TEXT,
    CALL_UNKNOWN_SPEAKER_TEXT,
    AUDIO_FORMAT,
    AUDIO_NO_SPEECH,
    AUDIO_REQUIRED,
    AUDIO_TOO_BIG,
    AUDIO_UNAVAILABLE,
    AUDIO_UNREADABLE,
    INVALID_DIFFICULTY,
)
from ..security import require_rate_limit
from ._utils import json_body

bp = Blueprint("calls", __name__, url_prefix="/api/calls")

SAMPLE_FILE = "calls_sample.txt"   # in config/: the call behind "Try a sample call"
_ERRORS = {
    CALL_UNREADABLE: CALL_UNREADABLE_TEXT,
    CALL_TOO_LONG: CALL_TOO_LONG_TEXT,
    CALL_TOO_SHORT: CALL_TOO_SHORT_TEXT,
    CALL_ONE_SPEAKER: CALL_ONE_SPEAKER_TEXT,
    UNKNOWN_SPEAKER: CALL_UNKNOWN_SPEAKER_TEXT,
}


def call_error(e: CallError):
    """The response for a transcript the reader refused (shared with /api/sop/check)."""
    message = _ERRORS[e.code].format(max_chars=CALL_LIMITS["max_chars"], name=e.detail)
    return jsonify({"error": message, "code": e.code}), 400


def _read():
    """(reading, None), or (None, error response) for a missing transcript or one the reader refuses."""
    data = json_body()
    text, rep = data.get("text"), data.get("rep")
    if not isinstance(text, str) or not text.strip():
        return None, (jsonify({"error": CALL_TEXT_REQUIRED, "code": CALL_UNREADABLE}), 400)
    try:
        return read_call(text, rep if isinstance(rep, str) and rep.strip() else None), None
    except CallError as e:
        return None, call_error(e)


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
    difficulty = json_body().get("difficulty") or reading.profile.difficulty
    try:
        return jsonify({"success": True, **sell_service.review_transcript(reading.history(), difficulty)})
    except InvalidDifficulty as e:
        return jsonify({"error": INVALID_DIFFICULTY.format(choices=", ".join(e.choices))}), 400


@bp.route("/transcribe", methods=["POST"])
@require_rate_limit("audio")
def transcribe_audio():
    """A call recording (multipart `file`) -> a transcript with speakers labelled "Speaker A" / "Speaker B",
    for the learner to check and read like any other (core/calls/audio.py). `labels_sure` is False when the AI's
    labels mostly could not be read, so the learner is asked to fix them. Nothing is stored.

    A recording past the engine's per-file limit is cut into parts and transcribed part by part
    (core/calls/audio_parts.py); that needs ffmpeg, so without it the engine's limit stays the cap."""
    # Recordings are far bigger than any other request: this route alone takes up to max_upload_bytes.
    request.max_content_length = TRANSCRIPTION["max_upload_bytes"] + MAX_REQUEST_BYTES
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"error": AUDIO_REQUIRED, "code": "AUDIO_REQUIRED"}), 400
    name = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
    ext = file_ext(name)
    if ext not in TRANSCRIPTION["formats"]:
        formats = ", ".join(TRANSCRIPTION["formats"])
        return jsonify({"error": AUDIO_FORMAT.format(formats=formats), "code": "AUDIO_FORMAT"}), 400
    size = _size(upload.stream)
    in_parts = size > TRANSCRIPTION["max_bytes"]
    cap = TRANSCRIPTION["max_upload_bytes"] if can_split() else TRANSCRIPTION["max_bytes"]
    if size > cap:
        return jsonify({"error": AUDIO_TOO_BIG.format(mb=cap // 1_000_000), "code": "AUDIO_TOO_BIG"}), 413
    try:
        segments = transcribe_in_parts(upload.stream, ext, transcribe) if in_parts else transcribe(upload.read(), name)
        if not segments:
            return jsonify({"error": AUDIO_NO_SPEECH, "code": "AUDIO_NO_SPEECH"}), 400
        router = ProviderRouter()

        def ask(prompt: str) -> str:
            return complete(router, [{"role": "user", "content": prompt}], **LLM["speaker_labels"])

        labels, sure = label_speakers(segments, ask, load_calls_config()["speaker_prompt"])
    except AudioUnreadable:
        return jsonify({"error": AUDIO_UNREADABLE, "code": "AUDIO_UNREADABLE"}), 400
    except (TranscriptionUnavailable, ProviderUnavailable):
        return jsonify({"error": AUDIO_UNAVAILABLE, "code": "AUDIO_UNAVAILABLE"}), 503
    return jsonify({"success": True, "text": as_transcript(segments, labels), "labels_sure": sure,
                    "filename": name.rsplit(".", 1)[0] + ".txt"})


def _size(stream) -> int:
    """The upload's size in bytes, without reading it into memory (Werkzeug keeps a big one in a temporary file)."""
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    return size
