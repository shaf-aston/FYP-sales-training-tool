"""Voice endpoints: speech-to-text (STT), text-to-speech (TTS) and full voice chat"""

import base64
import os

from flask import Blueprint, Response, jsonify, request

from core.constants import MAX_AUDIO_SIZE_BYTES, MAX_TTS_TEXT_LENGTH
from ..messages import VOICE_ERROR, VOICE_TTS_ERROR
from ..security import require_rate_limit

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

# Lazy-load voice provider to avoid startup failures if dependencies missing
_voice_provider = None


def init_routes(app, require_session_func, validate_message_func, bot_state_func):
    """Initialize voice routes with Flask app and callback functions"""
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.validate_message = validate_message_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]


def get_voice_provider():
    """Lazy-load VoiceProvider instance"""
    global _voice_provider
    if _voice_provider is None:
        from core.providers.voice_provider import VoiceProvider

        _voice_provider = VoiceProvider()
    return _voice_provider


_ALLOWED_AUDIO_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg"}


def _infer_audio_name(audio_file) -> str:
    filename = (audio_file.filename or "").strip()
    if filename:
        return filename

    mimetype = (audio_file.mimetype or "").lower()
    if "wav" in mimetype:
        return "audio.wav"
    if "mpeg" in mimetype or "mp3" in mimetype:
        return "audio.mp3"
    if "mp4" in mimetype or "m4a" in mimetype:
        return "audio.m4a"
    if "ogg" in mimetype:
        return "audio.ogg"
    return "audio.webm"


def _validate_audio_upload(audio_file):
    filename = _infer_audio_name(audio_file)
    _, ext = os.path.splitext(filename.lower())
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        return None, (
            jsonify({"error": f"Unsupported audio format: {ext or 'unknown'}"}),
            400,
        )

    audio_bytes = audio_file.read()
    if len(audio_bytes) == 0:
        return None, (jsonify({"error": "Empty audio file"}), 400)
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        return None, (
            jsonify(
                {
                    "error": f"Audio too large. Max: {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)}MB"
                }
            ),
            400,
        )
    return (audio_bytes, filename), None


@bp.route("/status", methods=["GET"])
def voice_status():
    """Check voice provider availability (STT + TTS)"""
    try:
        provider = get_voice_provider()
        return jsonify(
            {
                "success": True,
                "available": provider.is_stt_available()
                and provider.is_tts_available(),
                **provider.get_status(),
                "voices": provider.get_available_voices(),
            }
        )
    except ImportError as e:
        return jsonify(
            {
                "success": False,
                "available": False,
                "error": f"Voice dependencies not installed: {e}",
            }
        )
    except Exception as e:
        bp.app.logger.exception(f"Voice status error: {e}")  # type: ignore
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/transcribe", methods=["POST"])
@require_rate_limit("chat")
def voice_transcribe():
    """Transcribe uploaded audio to text"""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided. Use 'audio' field."}), 400

    audio_file = request.files["audio"]
    validated_audio, error = _validate_audio_upload(audio_file)
    if error:
        return error
    assert validated_audio is not None
    audio_bytes, inferred_name = validated_audio

    try:
        provider = get_voice_provider()
        result = provider.transcribe(audio_bytes, filename=inferred_name)

        if result.error:
            return jsonify(
                {
                    "success": False,
                    "error": result.error,
                    "provider": result.provider,
                    "rate_limited": result.rate_limited,
                    "fallback_recommended": result.fallback_recommended,
                }
            ), 500

        return jsonify(
            {
                "success": True,
                "text": result.text,
                "latency_ms": round(result.latency_ms, 1),
                "provider": result.provider,
            }
        )

    except Exception as e:
        bp.app.logger.exception(f"Voice transcribe error: {e}")  # type: ignore
        return jsonify({"error": "Couldn't catch that audio -- one more try?"}), 500


@bp.route("/synthesize", methods=["POST"])
@require_rate_limit("chat")
def voice_synthesize():
    """Turn text into speech audio"""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    voice = data.get("voice", "male_us")
    rate = data.get("rate", 0)  # Speech rate: -50 to +50 (percentage), default 0 = normal

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if len(text) > MAX_TTS_TEXT_LENGTH:
        return jsonify(
            {"error": f"Text too long. Max: {MAX_TTS_TEXT_LENGTH} characters"}
        ), 400

    try:
        provider = get_voice_provider()
        result = provider.synthesize(text, voice=voice, rate=rate)

        if result.error:
            return jsonify(
                {
                    "success": False,
                    "error": result.error,
                    "provider": result.provider,
                    "fallback_recommended": result.fallback_recommended,
                }
            ), 500

        return Response(
            result.audio_bytes,
            mimetype=result.content_type,
            headers={
                "Content-Disposition": "inline",
                "X-Latency-Ms": str(round(result.latency_ms, 1)),
                "X-Voice": result.voice,
            },
        )

    except Exception as e:
        bp.app.logger.exception(f"Voice synthesize error: {e}")  # type: ignore
        return jsonify({"error": VOICE_TTS_ERROR}), 500


@bp.route("/chat", methods=["POST"])
@require_rate_limit("chat")
def voice_chat():
    """Execute full voice loop: audio in -> chat -> audio out"""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided. Use 'audio' field."}), 400

    session_bot, error = bp.require_session()  # type: ignore
    if error:
        return error

    audio_file = request.files["audio"]
    voice = request.form.get("voice", "male_us")
    validated_audio, upload_error = _validate_audio_upload(audio_file)
    if upload_error:
        return upload_error
    assert validated_audio is not None
    audio_bytes, inferred_name = validated_audio

    try:
        voice_provider = get_voice_provider()

        # 1. Transcribe audio → text
        transcription = voice_provider.transcribe(audio_bytes, filename=inferred_name)

        if transcription.error:
            return jsonify(
                {
                    "success": False,
                    "error": f"Transcription failed: {transcription.error}",
                    "provider": transcription.provider,
                    "rate_limited": transcription.rate_limited,
                    "fallback_recommended": transcription.fallback_recommended,
                }
            ), 500

        user_message = transcription.text.strip()
        if not user_message:
            return jsonify(
                {"success": False, "error": "No speech detected in audio"}
            ), 400

        # Validate transcribed message (security check)
        clean_message, error = bp.validate_message(user_message)  # type: ignore
        if error:
            return error

        # 2. Chat with bot (reuse existing logic)
        response = session_bot.chat(clean_message)
        training = session_bot.generate_training(clean_message, response.content)

        # 3. Synthesize response → audio
        synthesis = voice_provider.synthesize(response.content, voice=voice)

        if synthesis.error:
            return jsonify(
                {
                    "success": False,
                    "error": f"Synthesis failed: {synthesis.error}",
                    "transcription": user_message,
                    "message": response.content,
                    **bp.bot_state(session_bot),  # type: ignore
                    "provider": response.provider,
                    "model": response.model,
                    "tts_provider": synthesis.provider,
                    "tts_fallback_recommended": synthesis.fallback_recommended,
                    "latency": {
                        "transcription_ms": round(transcription.latency_ms, 1),
                        "transcription_provider": transcription.provider,
                        "llm_ms": round(response.latency_ms, 1),
                        "synthesis_ms": round(synthesis.latency_ms, 1),
                        "total_ms": round(
                            transcription.latency_ms
                            + response.latency_ms
                            + synthesis.latency_ms,
                            1,
                        ),
                    },
                    "training": training,
                }
            ), 500

        # 4. Encode audio as base64 for JSON response
        audio_b64 = ""
        if synthesis.audio_bytes:
            audio_b64 = base64.b64encode(synthesis.audio_bytes).decode("utf-8")

        return jsonify(
            {
                "success": True,
                "transcription": user_message,
                "message": response.content,
                **bp.bot_state(session_bot),  # type: ignore
                "audio": audio_b64,
                "audio_type": synthesis.content_type,
                "voice": synthesis.voice,
                "tts_fallback_recommended": synthesis.fallback_recommended,
                "latency": {
                    "transcription_ms": round(transcription.latency_ms, 1),
                    "transcription_provider": transcription.provider,
                    "llm_ms": round(response.latency_ms, 1),
                    "synthesis_ms": round(synthesis.latency_ms, 1),
                    "total_ms": round(
                        transcription.latency_ms + response.latency_ms + synthesis.latency_ms,
                        1,
                    ),
                },
                "provider": response.provider,
                "model": response.model,
                "training": training,
            }
        )

    except Exception as e:
        bp.app.logger.exception(f"Voice chat error: {e}")  # type: ignore
        return jsonify({"error": VOICE_ERROR}), 500
