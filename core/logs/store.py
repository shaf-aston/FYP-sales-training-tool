"""The one writer: a record becomes a JSONL line in <logs dir>/<stream>/<UTC date>.jsonl, and a log line too."""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..constants import DEFAULT_LOGS_DIR
from ..env import ROOT_DIR, env_str

logger = logging.getLogger(__name__)
_lock = threading.Lock()  # gunicorn runs threads in one process; keep lines whole


def logs_dir() -> Path:
    """LOGS_DIR, relative to the repo root unless absolute."""
    return ROOT_DIR / (env_str("LOGS_DIR") or DEFAULT_LOGS_DIR)


def append(stream: str, record: dict) -> str:
    """Add one record to the stream's file for today. Best effort: a full disk never fails a turn."""
    now = datetime.now(timezone.utc)
    line = json.dumps({"at": now.isoformat(timespec="milliseconds"), **record}, ensure_ascii=False, default=str)
    path = logs_dir() / stream / f"{now:%Y-%m-%d}.jsonl"
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        logger.warning("could not write %s", path, exc_info=True)
    return line


def write(stream: str, record: dict) -> None:
    """Append the record and echo it to the server log as `<stream> <json>`."""
    logger.info("%s %s", stream, append(stream, record))
