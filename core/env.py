"""The only module that reads environment variables (and loads .env). Never log values."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

_TRUE_VALUES = {"1", "true", "yes", "on"}


def env_str(name: str, default: str | None = None) -> str | None:
    """Raw value of an env var, or `default` when unset."""
    return os.environ.get(name, default)


def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean env var. Unset gives `default`; 'false', '0' or '' give False."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES
