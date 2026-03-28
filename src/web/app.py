"""Flask application — registers blueprints and configures middleware.

This file has been refactored to use Flask blueprints for better organization.
Routes are now split across multiple blueprint modules in web/routes/:
- session.py: Session init/restore/reset/config/health
- chat.py: Chat conversation endpoints
- prospect.py: Prospect mode (role-reversal)
- voice.py: Voice mode (STT/TTS)
- analytics.py: Analytics, quizzes, knowledge management
- debug.py: Debug panel (development only)
"""

from flask import Flask, render_template
from flask_cors import CORS
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from chatbot.constants import MAX_PROSPECT_SESSIONS, PROSPECT_IDLE_MINUTES

# Security module (centralized security controls)
from web.security import (
    SecurityConfig,
    RateLimiter,
    PromptInjectionValidator,
    SecurityHeadersMiddleware,
    InputValidator,
    SessionSecurityManager,
    ClientIPExtractor,
    initialize_security,
    require_rate_limit,
)

# Disable .pyc file generation
sys.dont_write_bytecode = True

# Initialize Flask app
app = Flask(__name__)

# CORS: restrict to configured origins (default: Render deployment + localhost dev).
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments.
_allowed_origins = [
    o.strip() for o in
    os.environ.get('ALLOWED_ORIGINS', 'https://fyp-sales-training-tool.onrender.com,http://localhost:5000').split(',')
    if o.strip()
]
CORS(app, origins=_allowed_origins)


# ============================================================================
# Security Initialization
# ============================================================================

# Initialize security components (from security module)
rate_limiter, session_manager, injection_validator = initialize_security(
    app_logger=app.logger
)

# Wire security middleware
app.after_request(SecurityHeadersMiddleware.apply)
session_manager.start_background_cleanup()


# ============================================================================
# Prospect Session Management
# ============================================================================

# Use a second SessionSecurityManager instance for prospect sessions (eliminates code duplication)
prospect_session_manager = SessionSecurityManager(
    max_sessions=MAX_PROSPECT_SESSIONS,
    idle_minutes=PROSPECT_IDLE_MINUTES,
    cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
)
prospect_session_manager.start_background_cleanup()


# ============================================================================
# Helper Functions (Shared across blueprints via dependency injection)
# ============================================================================

def get_session(session_id):
    """Get chatbot, updating timestamp. Returns bot or None."""
    return session_manager.get(session_id)


def set_session(session_id, chatbot):
    """Store chatbot in memory."""
    session_manager.set(session_id, chatbot)


def delete_session(session_id):
    """Remove session from memory."""
    session_manager.delete(session_id)


def require_session():
    """Validate session header and return (bot, error_response).

    Returns:
        (bot, None) if valid session exists
        (None, error_response) if missing or invalid
    """
    from flask import request, jsonify

    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return None, (jsonify({"error": "Session ID required"}), 400)
    bot = get_session(session_id)
    if not bot:
        return None, (jsonify({"error": "Session not found", "code": "SESSION_EXPIRED"}), 400)
    return bot, None


def _validate_message(text: str):
    """Validate and sanitize message text. Returns (clean_text, error_response)."""
    return InputValidator.validate_message(
        text.strip(),
        injection_validator=injection_validator,
        max_length=SecurityConfig.MAX_MESSAGE_LENGTH
    )


def _bot_state(bot):
    """Extract common bot state fields for JSON responses.

    Returns:
        dict: {"stage": str, "strategy": str}
    """
    from chatbot.utils import Strategy
    # In discovery mode (intent strategy), stage is unset since real flow isn't determined yet
    # Once switched to consultative/transactional, show actual stage
    stage = "----" if bot.flow_engine.flow_type == Strategy.INTENT else bot.flow_engine.current_stage.upper()
    strategy = bot.flow_engine.flow_type.upper()

    return {
        "stage": stage,
        "strategy": strategy
    }


# ============================================================================
# Blueprint Registration
# ============================================================================

# Import blueprint modules
from web.routes import session, chat, prospect, voice, analytics, debug

# Initialize blueprints with dependency injection (pass helper functions)
session.init_routes(app, session_manager, get_session, set_session, delete_session, _bot_state)
chat.init_routes(app, get_session, require_session, _validate_message, _bot_state)
prospect.init_routes(app, prospect_session_manager, _validate_message)
voice.init_routes(app, require_session, _validate_message, _bot_state)
analytics.init_routes(app, require_session)
debug.init_routes(app, require_session)

# Register blueprints with Flask app
app.register_blueprint(session.bp)
app.register_blueprint(chat.bp)
app.register_blueprint(prospect.bp)
app.register_blueprint(voice.bp)
app.register_blueprint(analytics.bp)
app.register_blueprint(debug.bp)

# Note: Rate limiting is applied via @require_rate_limit decorators in blueprint files


# ============================================================================
# Page Routes (UI templates remain in main app)
# ============================================================================

@app.route('/favicon.ico')
def favicon():
    return ('', 204)


@app.route('/')
def home():
    """Serve the chat interface"""
    return render_template('index.html')


@app.route('/knowledge')
def knowledge_page():
    """Serve the knowledge base management page."""
    return render_template('knowledge.html')


# ============================================================================
# Debug Panel Guard
# ============================================================================

_DEBUG_ENABLED = os.environ.get('ENABLE_DEBUG_PANEL', '').lower() == 'true'

@app.before_request
def _guard_debug_endpoints():
    """Protect debug endpoints - only accessible with ENABLE_DEBUG_PANEL=true and from localhost."""
    from flask import request, jsonify

    if not request.path.startswith('/api/debug/'):
        return None

    if not _DEBUG_ENABLED:
        return jsonify({"error": "Debug endpoints disabled"}), 403

    client_ip = ClientIPExtractor.get_ip(request)
    if client_ip not in {'127.0.0.1', '::1', '::ffff:127.0.0.1'}:
        return jsonify({"error": "Debug endpoints are localhost-only"}), 403


# ============================================================================
# Error Handler
# ============================================================================

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Catch-all for unhandled exceptions — prevents stack trace leakage.

    Re-raises HTTP exceptions (4xx, 5xx) so Flask handles them normally.
    Only catches truly unexpected errors (e.g., unhandled ValueError, TypeError).
    """
    from flask import jsonify
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e  # Let Flask handle 400, 404, etc. normally
    app.logger.exception("Unhandled error")
    return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# Application Startup
# ============================================================================

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)
