"""The only place backend code reads environment variables."""

import os

DEFAULT_ALLOWED_ORIGINS = "https://fyp-sales-training-tool.onrender.com,http://localhost:5000"
_TRUE_VALUES = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean env var. Unset gives `default`; 'false', '0' or '' give False."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def is_flask_debug() -> bool:
    return env_flag("FLASK_DEBUG")


def is_reloader_child() -> bool:
    return env_flag("WERKZEUG_RUN_MAIN")

