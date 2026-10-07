"""Flask application entrypoint."""

import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

# Makes `backend` and `core` importable when run directly: `python backend/app.py`
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.constants import BUYER_IDLE_MINUTES, MAX_BUYER_SESSIONS  # noqa: E402
from core.script_engine.seller import shared_embedder  # noqa: E402
from backend.messages import INTERNAL_SERVER_ERROR  # noqa: E402
from backend.security import (  # noqa: E402
    SecurityConfig,
    SecurityHeadersMiddleware,
    SessionSecurityManager,
    initialize_security,
)
from backend import settings  # noqa: E402
from backend.routes import buy, knowledge, monitoring, old_paths, sell  # noqa: E402
from backend.routes._utils import Sessions  # noqa: E402

app = Flask(
    __name__,
    static_folder=None,  # the web app is served by `web_app` below
)

# CORS: restrict to configured origins (default: Render deployment + localhost dev)
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments
CORS(app, origins=settings.allowed_origins())


rate_limiter, session_manager = initialize_security(
    app_logger=app.logger
)

app.after_request(SecurityHeadersMiddleware.apply)


# Sell-mode sessions (the AI buyer). `session_manager` above holds buy mode's AI sellers.
buyer_session_manager = SessionSecurityManager(
    max_sessions=MAX_BUYER_SESSIONS,
    idle_minutes=BUYER_IDLE_MINUTES,
    cleanup_interval=SecurityConfig.CLEANUP_INTERVAL_SECONDS,
    manager_name="buyer sessions",
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
    buyer_session_manager.start_background_cleanup()
    # load the local meaning model now, so the first call doesn't wait ~2 s for it
    threading.Thread(target=shared_embedder, daemon=True, name="embedder-warmup").start()


app.extensions["sessions"] = Sessions(seller=session_manager, buyer=buyer_session_manager)

app.register_blueprint(buy.bp)  # /api/buy/*: learner is the customer
app.register_blueprint(sell.bp)  # /api/sell/*: learner is the salesperson
app.register_blueprint(knowledge.bp)  # /api/knowledge
app.register_blueprint(monitoring.bp)  # /api/health, /api/analytics/*, /api/feedback

# Old paths (/api/init, /api/test/*, /api/prospect/* ...): remove once the
# deployed web uses /api/buy and /api/sell. See backend/routes/old_paths.py.
old_paths.register_old_paths(app)

# Note: Rate limiting is applied via @require_rate_limit decorators in blueprint files


WEB_BUILD_DIR = ROOT_DIR / "web" / "out"

# Old page URLs -> their new pages (permanent redirects, query string kept).
OLD_PAGES = {
    "practice": "/buy/",
    "practice/sell": "/sell/",
}


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def web_app(path: str):
    """Serve the built Next.js app (web/out). Rebuild with `npm run build` in web/."""
    from flask import abort, redirect, request, send_from_directory
    from werkzeug.exceptions import NotFound

    if path.startswith("api/"):
        abort(404)
    old_page = OLD_PAGES.get(path.rstrip("/"))
    if old_page:
        query = request.query_string.decode("utf-8", "replace")
        return redirect(f"{old_page}?{query}" if query else old_page, 301)
    if not WEB_BUILD_DIR.is_dir():
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
