"""Flask application: registers blueprints and configures middleware

This file has been refactored to use Flask blueprints for better organization
Routes are now split across multiple blueprint modules in web/routes/
- session.py: Session init/restore/reset/config/health
- chat.py: Chat conversation endpoints
- prospect.py: Prospect mode (role-reversal)
- voice.py: Voice mode (STT/TTS)
- analytics.py: Analytics, quizzes, knowledge management
- debug.py: Advanced options panel (development only)
"""
# ruff: noqa: E402 — sys.path must be set before any chatbot imports

import os
import sys

# adds src/ to path so chatbot imports resolve
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402
from flask import Flask, render_template, send_from_directory  # noqa: E402
from flask_cors import CORS  # noqa: E402

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from chatbot.constants import MAX_PROSPECT_SESSIONS, PROSPECT_IDLE_MINUTES  # noqa: E402

# Security module (centralized security controls)
from web.security import (  # noqa: E402
    ClientIPExtractor,
    InputValidator,
    SecurityConfig,
    SecurityHeadersMiddleware,
    SessionSecurityManager,
    initialize_security,
)

# Disable .pyc file generation
sys.dont_write_bytecode = True

# Initialize Flask app
app = Flask(__name__)

# CORS: restrict to configured origins (default: Render deployment + localhost dev)
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments
_allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "https://fyp-sales-training-tool.onrender.com,http://localhost:5000"
    ).split(",")
    if o.strip()
]
CORS(app, origins=_allowed_origins)


rate_limiter, session_manager, injection_validator = initialize_security(app_logger=app.logger)

app.after_request(SecurityHeadersMiddleware.apply)
session_manager.start_background_cleanup()


prospect_session_manager = SessionSecurityManager(
    max_sessions=MAX_PROSPECT_SESSIONS,
    idle_minutes=PROSPECT_IDLE_MINUTES,
    cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
)
prospect_session_manager.start_background_cleanup()


def get_session(session_id):
    """Get chatbot, updating timestamp. Returns bot or None"""
    return session_manager.get(session_id)


def set_session(session_id, chatbot):
    """Store chatbot in memory"""
    session_manager.set(session_id, chatbot)


def delete_session(session_id):
    """Remove session from memory"""
    session_manager.delete(session_id)


def require_session():
    """Pull the bot for this session, or return an error response if the session is missing"""
    from flask import jsonify, request

    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        return None, (jsonify({"error": "Session ID required"}), 400)
    bot = get_session(session_id)
    if not bot:
        return None, (jsonify({"error": "Session not found", "code": "SESSION_EXPIRED"}), 400)
    return bot, None


def _validate_message(text):
    """Validate and sanitize message text. Returns (clean_text, error_response)"""
    from flask import jsonify

    if not text or not isinstance(text, str):
        return None, (jsonify({"error": "Message required"}), 400)
    return InputValidator.validate_message(
        text.strip(), injection_validator=injection_validator, max_length=SecurityConfig.MAX_MESSAGE_LENGTH
    )


def _bot_state(bot):
    """Common stage/strategy fields for JSON responses"""
    from chatbot.utils import Strategy

    # In discovery mode (intent strategy), stage is unset since real flow isn't determined yet
    # Once switched to consultative/transactional, show actual stage
    stage = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return {"stage": stage, "strategy": strategy}


# Blueprint modules must be imported AFTER app initialization (app needs to exist)
# E402 suppressed because this is an intentional Flask pattern

from web.routes import analytics, chat, debug, prospect, session, voice  # noqa: E402

session.init_routes(app, session_manager, get_session, set_session, delete_session, _bot_state)
chat.init_routes(app, get_session, require_session, _validate_message, _bot_state)
prospect.init_routes(app, prospect_session_manager, _validate_message)
voice.init_routes(app, require_session, _validate_message, _bot_state)
analytics.init_routes(app, require_session, _bot_state)
debug.init_routes(app, require_session)

app.register_blueprint(session.bp)
app.register_blueprint(chat.bp)
app.register_blueprint(prospect.bp)
app.register_blueprint(voice.bp)
app.register_blueprint(analytics.bp)
app.register_blueprint(debug.bp)

# Note: Rate limiting is applied via @require_rate_limit decorators in blueprint files


@app.route("/favicon.ico")
def favicon():
    # Tests expect /favicon.ico to return 204 when testing — keep that behavior
    if app.config.get("TESTING"):
        return ("", 204)

    # Serve favicon from the Flask static folder if present
    try:
        static_dir = app.static_folder
        if not static_dir:
            return ("", 204)
        ico_path = os.path.join(static_dir, "favicon.ico")
        png_path = os.path.join(static_dir, "favicon.png")
        if os.path.exists(ico_path):
            return send_from_directory(static_dir, "favicon.ico")
        if os.path.exists(png_path):
            return send_from_directory(static_dir, "favicon.png")
    except Exception:
        app.logger.debug("Favicon serve failed", exc_info=True)
    return ("", 204)


@app.route("/")
def home():
    """Serve the chat interface (seller mode)"""
    return render_template("index.html", mode="seller", debug_enabled=_DEBUG_ENABLED)


@app.route("/prospect")
def prospect_page():
    """Serve the chat interface in prospect mode"""
    return render_template("index.html", mode="prospect", debug_enabled=_DEBUG_ENABLED)


@app.route("/knowledge")
def knowledge_page():
    """Serve the knowledge base management page"""
    from flask import request

    mode = (request.args.get("mode") or "").strip().lower()
    if mode != "prospect":
        mode = ""
    return render_template("knowledge.html", mode=mode)


_DEBUG_ENABLED = os.environ.get("ENABLE_DEBUG_PANEL", "").lower() == "true"


@app.before_request
def _guard_debug_endpoints():
    """Protect debug endpoints - only accessible with ENABLE_DEBUG_PANEL=true and from localhost"""
    from flask import jsonify, request

    if not request.path.startswith("/api/debug/"):
        return None

    if not _DEBUG_ENABLED:
        return jsonify({"error": "Debug endpoints disabled"}), 403

    client_ip = ClientIPExtractor.get_ip(request)
    if client_ip not in {"127.0.0.1", "::1", "::ffff:127.0.0.1"}:
        return jsonify({"error": "Debug endpoints are localhost-only"}), 403


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Catch-all for unhandled exceptions. HTTP exceptions pass through unchanged"""
    from flask import jsonify
    from werkzeug.exceptions import HTTPException

    if isinstance(e, HTTPException):
        return e  # Let Flask handle 400, 404, etc. normally
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=5000)
