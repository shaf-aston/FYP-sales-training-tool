"""Flask application entrypoint."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, render_template
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

if __package__ in (None, ""):
    # Support direct execution: `python backend/app.py`
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from core.constants import MAX_PROSPECT_SESSIONS, PROSPECT_IDLE_MINUTES, UNDETERMINED_STAGE
    from backend.messages import (
        INTERNAL_SERVER_ERROR,
        MESSAGE_REQUIRED,
        SESSION_NOT_FOUND,
    )
    from backend.security import (
        InputValidator,
        SecurityConfig,
        SecurityHeadersMiddleware,
        SessionSecurityManager,
        initialize_security,
    )
    from backend.routes import analytics, chat, prospect, session
else:
    from core.constants import MAX_PROSPECT_SESSIONS, PROSPECT_IDLE_MINUTES, UNDETERMINED_STAGE
    from .messages import (
        INTERNAL_SERVER_ERROR,
        MESSAGE_REQUIRED,
        SESSION_NOT_FOUND,
    )
    from .security import (
        InputValidator,
        SecurityConfig,
        SecurityHeadersMiddleware,
        SessionSecurityManager,
        initialize_security,
    )
    from .routes import analytics, chat, prospect, session

app = Flask(
    __name__,
    template_folder=str(ROOT_DIR / "frontend" / "templates"),
    static_folder=str(ROOT_DIR / "frontend" / "static"),
)

# CORS: restrict to configured origins (default: Render deployment + localhost dev)
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments
_allowed_origins = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://fyp-sales-training-tool.onrender.com,http://localhost:5000",
    ).split(",")
    if o.strip()
]
CORS(app, origins=_allowed_origins)


rate_limiter, session_manager, injection_validator = initialize_security(
    app_logger=app.logger
)

app.after_request(SecurityHeadersMiddleware.apply)


prospect_session_manager = SessionSecurityManager(
    max_sessions=MAX_PROSPECT_SESSIONS,
    idle_minutes=PROSPECT_IDLE_MINUTES,
    cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
    manager_name="prospect sessions",
)


def _should_start_background_cleanup() -> bool:
    """Only start cleanup threads in the serving process."""
    if app.config.get("TESTING"):
        return False

    is_debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    if not is_debug_mode:
        return True

    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


if _should_start_background_cleanup():
    session_manager.start_background_cleanup()
    prospect_session_manager.start_background_cleanup()


def _require_session():
    """Pull the bot for this session, or return an error response if the session is missing"""
    from flask import jsonify, request

    session_id = request.headers.get("X-Session-ID")
    session_error = InputValidator.validate_session_id(session_id)
    if session_error:
        return None, session_error
    bot = session_manager.get(session_id)
    if not bot:
        return None, (
            jsonify({"error": SESSION_NOT_FOUND, "code": "SESSION_EXPIRED"}),
            400,
        )
    return bot, None


def _validate_message(message_text):
    """Validate and sanitize message text. Returns (clean_text, error_response)"""
    from flask import jsonify

    if not message_text or not isinstance(message_text, str):
        return None, (jsonify({"error": MESSAGE_REQUIRED}), 400)
    return InputValidator.validate_message(
        message_text.strip(),
        injection_validator=injection_validator,
        max_length=SecurityConfig.MAX_MESSAGE_LENGTH,
    )


def _bot_state(session_bot):
    """Common stage/strategy fields for JSON responses"""
    from core.utils import Strategy

    # In discovery mode (intent strategy), stage is unset since real flow isn't determined yet
    # Once switched to consultative/transactional, show actual stage
    stage = (
        UNDETERMINED_STAGE
        if session_bot.flow_engine.flow_type == Strategy.INTENT
        else session_bot.flow_engine.current_stage.upper()
    )
    strategy = session_bot.flow_engine.flow_type.upper()

    return {"stage": stage, "strategy": strategy}


session.init_routes(
    app, session_manager, session_manager.get, session_manager.set, session_manager.delete, _bot_state
)
chat.init_routes(app, session_manager.get, _require_session, _validate_message, _bot_state)
prospect.init_routes(app, prospect_session_manager, _validate_message)
analytics.init_routes(app, _require_session, _bot_state)

app.register_blueprint(session.bp)
app.register_blueprint(chat.bp)
app.register_blueprint(prospect.bp)
app.register_blueprint(analytics.bp)

# Note: Rate limiting is applied via @require_rate_limit decorators in blueprint files


def _prospect_product_options():
    """Build the list of {id, label} dicts for the prospect-practice dropdown.

    Source of truth: prospect_config.yaml (personas) + product_config.yaml (names).
    Rendered directly into index.html by Jinja -- no client-side fetch needed.
    """
    try:
        from core.loader import load_prospect_config, load_product_config

        personas = load_prospect_config().get("personas", {})
        products = load_product_config().get("products", {})

        options = []
        for product_id, persona_list in personas.items():
            # Skip the generic bucket and any product that has no prospect personas defined.
            if product_id == "general" or not persona_list:
                continue
            label = (
                products.get(product_id, {}).get("name")
                or product_id.replace("_", " ").title()
            )
            options.append({"id": product_id, "label": label})
        return options
    except Exception:
        app.logger.exception("Failed to build prospect product options")
        return []


def _prospect_product_groups():
    """Build curated prospect-mode dropdown groups split by sales motion."""
    try:
        from core.loader import load_product_config, load_prospect_config

        personas = load_prospect_config().get("personas", {})
        products = load_product_config().get("products", {})

        curated_ids = {
            "transactional": [
                "luxury_cars",
                "premium_electronics",
                "watches",
                "travel",
                "fashion",
            ],
            "consultative": [
                "b2b_saas",
                "high_ticket_sales_mentorship",
                "financial_services",
                "education",
                "healthcare_services",
            ],
        }

        grouped_options = {}
        for strategy, product_ids in curated_ids.items():
            options = []
            for product_id in product_ids:
                if product_id not in personas or not personas.get(product_id):
                    continue
                product_info = products.get(product_id, {})
                options.append(
                    {
                        "id": product_id,
                        "label": product_info.get("name")
                        or product_id.replace("_", " ").title(),
                    }
                )
            grouped_options[strategy] = options
        return grouped_options
    except Exception:
        app.logger.exception("Failed to build prospect product groups")
        return {"transactional": [], "consultative": []}


def _render_index(mode: str):
    """Render the chat page; product dropdown is populated server-side."""
    # Keep UI flow-controls consistent with the privileged-mutation guard in `backend/security.py`.
    require_admin = app.config.get(
        "REQUIRE_ADMIN_FOR_STAGE_MUTATION",
        os.environ.get("REQUIRE_ADMIN_FOR_STAGE_MUTATION", "").strip().lower()
        in {"1", "true", "yes", "on"},
    )
    return render_template(
        "index.html",
        mode=mode,
        prospect_products=_prospect_product_options(),
        prospect_product_groups=_prospect_product_groups(),
        flow_controls_enabled=not require_admin,
    )


@app.route("/")
def home():
    """Serve the chat interface (seller mode)."""
    return _render_index("seller")


@app.route("/prospect")
def prospect_page():
    """Serve the chat interface in prospect mode."""
    return _render_index("prospect")


@app.route("/knowledge")
def knowledge_page():
    """Serve the knowledge base management page"""
    from flask import request

    mode = (request.args.get("mode") or "").strip().lower()
    if mode != "prospect":
        mode = ""
    return render_template("knowledge.html", mode=mode)


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Catch-all for unhandled exceptions. HTTP exceptions pass through unchanged"""
    from flask import jsonify
    from werkzeug.exceptions import HTTPException

    if isinstance(e, HTTPException):
        return e  # Let Flask handle 400, 404, etc. normally
    app.logger.exception("Unhandled error")
    return jsonify({"error": INTERNAL_SERVER_ERROR}), 500


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true", port=5000)
