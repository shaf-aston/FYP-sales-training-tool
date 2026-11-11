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

from backend.messages import INTERNAL_SERVER_ERROR, REQUEST_TOO_LARGE  # noqa: E402
from backend.request_log import RequestLog, configure_logging  # noqa: E402
from backend.auth import init_auth  # noqa: E402
from backend.routes import account, buy, calls, knowledge, monitoring, sell, speech, team  # noqa: E402
from backend.routes._utils import Sessions  # noqa: E402
from backend.security import (  # noqa: E402
    SecurityHeadersMiddleware,
    SessionStore,
    initialize_security,
)
from core.infra.constants import (  # noqa: E402
    BUYER_IDLE_MINUTES,
    CLEANUP_INTERVAL_SECONDS,
    DEFAULT_ALLOWED_ORIGINS,
    MAX_BUYER_SESSIONS,
    MAX_REQUEST_BYTES,
    MAX_SELLER_SESSIONS,
    SELLER_IDLE_MINUTES,
    SERVER_PORT,
)
from core.infra.env import env_flag, env_str  # noqa: E402
from core.buy_mode.script_engine.seller import shared_embedder  # noqa: E402

configure_logging()  # before Flask, so the app's logger shares the one handler

app = Flask(
    __name__,
    static_folder=None,  # the web app is served by `web_app` below
)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES  # a bigger body gets 413 before any route reads it
init_auth(app)  # login cookie (backend/auth.py)

# CORS: restrict to configured origins (default: the Vercel site + localhost dev)
# Override via ALLOWED_ORIGINS env var (comma-separated) for other deployments
allowed_origins = env_str("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
CORS(app, origins=[o.strip() for o in allowed_origins.split(",") if o.strip()])


initialize_security(app_logger=app.logger)

app.wsgi_app = RequestLog(app.wsgi_app)  # times every /api request

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
app.register_blueprint(monitoring.bp)  # /api/health, /api/feedback
app.register_blueprint(speech.bp)  # /api/speech: replies read aloud
app.register_blueprint(calls.bp)  # /api/calls/*: read and review an uploaded real call
app.register_blueprint(account.bp)  # /api/account/*: sign up, log in, skill history, saved prospects
app.register_blueprint(team.bp)  # /api/team/*: teams, invite codes, members


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


@app.errorhandler(413)
def handle_too_large(_e):
    """An oversized body (limits.yaml max_request_bytes) gets JSON like every other API error."""
    from flask import jsonify

    return jsonify({"error": REQUEST_TOO_LARGE, "code": "REQUEST_TOO_LARGE"}), 413


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
