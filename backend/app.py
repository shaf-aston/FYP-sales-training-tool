"""Flask application entrypoint."""

import sys
import threading
from pathlib import Path

from flask import Flask
from flask_cors import CORS

ROOT_DIR = Path(__file__).resolve().parent.parent

# Makes `backend` and `core` importable when run directly: `python backend/app.py`
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.messages import INTERNAL_SERVER_ERROR  # noqa: E402
from backend.routes import buy, knowledge, monitoring, sell  # noqa: E402
from backend.routes._utils import Sessions  # noqa: E402
from backend.security import (  # noqa: E402
    SecurityHeadersMiddleware,
    SessionStore,
    initialize_security,
)
from core.constants import (  # noqa: E402
    BUYER_IDLE_MINUTES,
    CLEANUP_INTERVAL_SECONDS,
    DEFAULT_ALLOWED_ORIGINS,
    MAX_BUYER_SESSIONS,
    MAX_SELLER_SESSIONS,
    SELLER_IDLE_MINUTES,
    SERVER_PORT,
)
from core.env import env_flag, env_str  # noqa: E402
from core.script_engine.seller import shared_embedder  # noqa: E402

app = Flask(
    __name__,
    static_folder=None,  # the web app is served by `web_app` below
)

# CORS: restrict to configured origins (default: Render deployment + localhost dev)
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments
allowed_origins = env_str("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
CORS(app, origins=[o.strip() for o in allowed_origins.split(",") if o.strip()])


initialize_security(app_logger=app.logger)

app.after_request(SecurityHeadersMiddleware.apply)

seller_sessions = SessionStore(
    max_sessions=MAX_SELLER_SESSIONS,
    idle_minutes=SELLER_IDLE_MINUTES,
    cleanup_interval=CLEANUP_INTERVAL_SECONDS,
    name="seller sessions",
)
buyer_sessions = SessionStore(
    max_sessions=MAX_BUYER_SESSIONS,
    idle_minutes=BUYER_IDLE_MINUTES,
    cleanup_interval=CLEANUP_INTERVAL_SECONDS,
    name="buyer sessions",
)


def _should_start_background_cleanup() -> bool:
    """Only start cleanup threads in the serving process."""
    if app.config.get("TESTING"):
        return False

    if not env_flag("FLASK_DEBUG"):
        return True

    return env_flag("WERKZEUG_RUN_MAIN")


if _should_start_background_cleanup():
    seller_sessions.start_background_cleanup()
    buyer_sessions.start_background_cleanup()
    # load the local meaning model now, so the first call doesn't wait ~2 s for it
    threading.Thread(target=shared_embedder, daemon=True, name="embedder-warmup").start()


app.extensions["sessions"] = Sessions(seller=seller_sessions, buyer=buyer_sessions)

app.register_blueprint(buy.bp)  # /api/buy/*: learner is the customer
app.register_blueprint(sell.bp)  # /api/sell/*: learner is the salesperson
app.register_blueprint(knowledge.bp)  # /api/knowledge
app.register_blueprint(monitoring.bp)  # /api/health, /api/analytics/*, /api/feedback


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
    app.run(debug=env_flag("FLASK_DEBUG"), port=SERVER_PORT)
