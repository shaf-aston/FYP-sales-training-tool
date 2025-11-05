import os
import json
import logging
from datetime import datetime
from typing import Dict

from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "conversation_events.log"

# Simple file logger for analytics/events
logger = logging.getLogger("analytics_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE)
formatter = logging.Formatter("%(asctime)s - %(message)s")
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(file_handler)

# Try optional DB integration
try:
    from .persona_db_service import _get_conn, init_db
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False


def log_event(event: Dict):
    """Persist an event to the local log file and optionally to the database.

    Event shape:
      {
        'user_id': 'user123',
        'event_type': 'message_sent' | 'message_received' | 'session_started' | 'session_ended',
        'payload': {...}
      }
    """
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "event": event,
    }
    # append to local file as JSON lines for easy ingestion
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        logger.exception("Failed writing analytics event to file")

    # Optional DB insert
    if DB_AVAILABLE:
        try:
            # Ensure DB tables exist
            init_db()
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO analytics_events (user_id, event_type, payload) VALUES (%s, %s, %s);",
                (event.get("user_id"), event.get("event_type"), json.dumps(event.get("payload") or {})),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            logger.exception("Failed writing analytics event to DB")
