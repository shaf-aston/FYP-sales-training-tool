"""Voice endpoints: Handled via Puter.js on client. Only state routing remains."""

from flask import Blueprint, jsonify, request

from web.messages import VOICE_ERROR

bp = Blueprint("voice", __name__, url_prefix="/api/voice")

def init_routes(app, require_session_func, validate_message_func, bot_state_func):
    """hook up voice routes"""
    bp.app = app  # type: ignore[attr-defined]
    bp.require_session = require_session_func  # type: ignore[attr-defined]
    bp.validate_message = validate_message_func  # type: ignore[attr-defined]
    bp.bot_state = bot_state_func  # type: ignore[attr-defined]

@bp.route("/status", methods=["GET"])
def voice_status():
    """Client handles Voice status directly via Puter.js"""
    return jsonify({
        "success": True,
        "available": True,
        "stt_deepgram": False,
        "stt_deepgram_rate_limited": False,
        "tts_edge": False,
        "stt_available": True,
        "tts_available": True,
        "voices": {
            "puter": "Puter.js"
        }
    })

@bp.route("/chat", methods=["POST"])
def voice_chat():
    """full voice loop: audio in -> chat -> audio out"""
    data = request.json or {}
    user_message = data.get("message", "").strip()
    voice = data.get("voice", "puter")

    if not user_message:
        return jsonify({"error": "No message provided."}), 400

    bot, err = bp.require_session()  # type: ignore
    if err:
        return err

    try:
        # Validate transcribed message (security check)
        clean_message, val_err = bp.validate_message(user_message)  # type: ignore
        if val_err:
            return val_err

        # 2. Chat with bot (reuse existing logic)
        response = bot.chat(clean_message)
        training = bot.generate_training(clean_message, response.content)

        return jsonify(
            {
                "success": True,
                "transcription": user_message,
                "message": response.content,
                **bp.bot_state(bot),  # type: ignore
                "audio": "", # Deprecated, handled strictly on client
                "audio_type": "",
                "voice": "puter.js",
                "latency": {
                    "transcription_ms": 0, # Client side handled
                    "transcription_provider": "puter.js",
                    "llm_ms": round(response.latency_ms, 1),
                    "synthesis_ms": 0, # Client side handled
                    "total_ms": round(response.latency_ms, 1),
                },
                "provider": response.provider,
                "model": response.model,
                "training": training,
            }
        )

    except Exception as e:
        bp.app.logger.exception(f"Voice chat error: {e}")  # type: ignore
        return jsonify({"error": VOICE_ERROR}), 500
