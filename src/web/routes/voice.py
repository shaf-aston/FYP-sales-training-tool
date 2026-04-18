"""Voice endpoints: speech-to-text (STT), text-to-speech (TTS), and full voice chat"""

import base64

from flask import Blueprint, Response, jsonify, request

from chatbot.constants import MAX_AUDIO_SIZE_BYTES, MAX_TTS_TEXT_LENGTH
from web.messages import VOICE_ERROR, VOICE_TTS_ERROR

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

# Lazy-load voice provider to avoid startup failures if dependencies missing
_voice_provider = None


def init_routes(app, require_session_func, validate_message_func, bot_state_func):
    """hook up voice routes"""
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.validate_message = validate_message_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]


def get_voice_provider():
    """Lazy-load VoiceProvider instance"""
    global _voice_provider
    if _voice_provider is None:
        from chatbot.providers.voice_provider import VoiceProvider

        _voice_provider = VoiceProvider()
    return _voice_provider


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
def voice_transcribe():
    """transcribe uploaded audio to text"""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided. Use 'audio' field."}), 400

    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()

    # Validate size (max 25MB)
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        return jsonify(
            {
                "error": f"Audio too large. Max: {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)}MB"
            }
        ), 400

    if len(audio_bytes) == 0:
        return jsonify({"error": "Empty audio file"}), 400

    try:
        provider = get_voice_provider()
        result = provider.transcribe(
            audio_bytes, filename=audio_file.filename or "audio.webm"
        )

        if result.error:
            return jsonify(
                {
                    "success": False,
                    "error": result.error,
                    "provider": result.provider,
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
def voice_synthesize():
    """turn text into speech audio"""
    data = request.json or {}
    text = (data.get("text") or "").strip()
    voice = data.get("voice", "male_us")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if len(text) > MAX_TTS_TEXT_LENGTH:
        return jsonify(
            {"error": f"Text too long. Max: {MAX_TTS_TEXT_LENGTH} characters"}
        ), 400

    try:
        provider = get_voice_provider()
        result = provider.synthesize(text, voice=voice)

        if result.error:
            return jsonify({"success": False, "error": result.error}), 500

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
def voice_chat():
    """full voice loop: audio in -> chat -> audio out"""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided. Use 'audio' field."}), 400

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    audio_file = request.files["audio"]
    audio_bytes = audio_file.read()
    voice = request.form.get("voice", "male_us")

    # Validate audio
    if len(audio_bytes) == 0:
        return jsonify({"error": "Empty audio file"}), 400
    if len(audio_bytes) > MAX_AUDIO_SIZE_BYTES:
        return jsonify({"error": "Audio too large. Max: 25MB"}), 400

    try:
        voice_provider = get_voice_provider()

        # 1. Transcribe audio → text
        transcription = voice_provider.transcribe(
            audio_bytes, filename=audio_file.filename or "audio.webm"
        )

        if transcription.error:
            return jsonify(
                {
                    "success": False,
                    "error": f"Transcription failed: {transcription.error}",
                    "provider": transcription.provider,
                }
            ), 500

        user_message = transcription.text.strip()
        if not user_message:
            return jsonify(
                {"success": False, "error": "No speech detected in audio"}
            ), 400

        # Validate transcribed message (security check)
        clean_message, val_err = bp.validate_message(user_message)  # type: ignore
        if val_err:
            return val_err

        # 2. Chat with bot (reuse existing logic)
        response = bot.chat(clean_message)
        training = bot.generate_training(clean_message, response.content)

        # 3. Synthesize response → audio
        synthesis = voice_provider.synthesize(response.content, voice=voice)

        # 4. Encode audio as base64 for JSON response
        audio_b64 = ""
        if not synthesis.error and synthesis.audio_bytes:
            audio_b64 = base64.b64encode(synthesis.audio_bytes).decode("utf-8")

        return jsonify(
            {
                "success": True,
                "transcription": user_message,
                "message": response.content,
                **bp.bot_state(bot),  # type: ignore
                "audio": audio_b64,
                "audio_type": synthesis.content_type if not synthesis.error else "",
                "voice": synthesis.voice,
                "latency": {
                    "transcription_ms": round(transcription.latency_ms, 1),
                    "transcription_provider": transcription.provider,
                    "llm_ms": round(response.latency_ms, 1),
                    "synthesis_ms": round(synthesis.latency_ms, 1)
                    if not synthesis.error
                    else 0,
                    "total_ms": round(
                        transcription.latency_ms
                        + response.latency_ms
                        + (synthesis.latency_ms if not synthesis.error else 0),
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
