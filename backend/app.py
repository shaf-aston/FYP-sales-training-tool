"""Flask application entrypoint."""

import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

# Makes `backend` and `core` importable when run directly: `python backend/app.py`
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.constants import MAX_PROSPECT_SESSIONS, PROSPECT_IDLE_MINUTES, UNDETERMINED_STAGE  # noqa: E402
from backend.messages import INTERNAL_SERVER_ERROR, MESSAGE_REQUIRED  # noqa: E402
from backend.security import (  # noqa: E402
    InputValidator,
    SecurityConfig,
    SecurityHeadersMiddleware,
    SessionSecurityManager,
    initialize_security,
)
from backend import settings  # noqa: E402
from backend.routes import analytics, chat, prospect, session  # noqa: E402
from backend.routes._utils import make_require_session  # noqa: E402

app = Flask(
    __name__,
    static_folder=None,  # the web app is served by `web_app` below
)

# CORS: restrict to configured origins (default: Render deployment + localhost dev)
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments
CORS(app, origins=settings.allowed_origins())


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

    if not settings.is_flask_debug():
        return True

    return settings.is_reloader_child()


if _should_start_background_cleanup():
    session_manager.start_background_cleanup()
    prospect_session_manager.start_background_cleanup()


_require_session = make_require_session(session_manager.get)


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
    app, session_manager, session_manager.get, session_manager.set, session_manager.delete,
    _bot_state, _require_session,
)
chat.init_routes(app, session_manager.get, _require_session, _validate_message, _bot_state)
prospect.init_routes(app, prospect_session_manager, _validate_message)
analytics.init_routes(app, _require_session, _bot_state)

app.register_blueprint(session.bp)
app.register_blueprint(chat.bp)
app.register_blueprint(prospect.bp)
app.register_blueprint(analytics.bp)

# Note: Rate limiting is applied via @require_rate_limit decorators in blueprint files


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


@app.route("/api/prospect/product-groups")
def prospect_product_groups():
    """Curated prospect dropdown groups as JSON (the React app has no Jinja)."""
    from flask import jsonify

    return jsonify({"success": True, "groups": _prospect_product_groups()})


WEB_BUILD_DIR = ROOT_DIR / "web" / "out"


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def web_app(path: str):
    """Serve the built Next.js app (web/out). Rebuild with `npm run build` in web/."""
    from flask import abort, send_from_directory
    from werkzeug.exceptions import NotFound

    if path.startswith("api/") or not WEB_BUILD_DIR.is_dir():
        abort(404)
    # send_from_directory rejects traversal; a folder request falls back to its index.html.
    for candidate in (path or "index.html", f"{path.rstrip('/')}/index.html"):
        try:
            return send_from_directory(WEB_BUILD_DIR, candidate)
        except NotFound:
            continue
    return send_from_directory(WEB_BUILD_DIR, "404.html"), 404


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
    app.run(debug=settings.is_flask_debug(), port=5000)
