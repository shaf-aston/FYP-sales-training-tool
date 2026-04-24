"""Persist prospect session state to disk atomically."""

import json
import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sessions"))
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _is_valid_session_id(session_id: str) -> bool:
    if not isinstance(session_id, str) or not session_id:
        return False
    return bool(re.match(r"^[A-Za-z0-9_-]+$", session_id))


def _get_safe_path(session_id: str) -> Optional[str]:
    if not _is_valid_session_id(session_id):
        logger.warning("Rejected invalid prospect session_id: %r", session_id)
        return None

    filepath = os.path.abspath(os.path.join(SESSIONS_DIR, f"{session_id}.prospect.json"))
    if not filepath.startswith(os.path.abspath(SESSIONS_DIR) + os.sep):
        logger.warning("Blocked prospect path traversal attempt: %r", filepath)
        return None

    return filepath


class ProspectSessionPersistence:
    """Atomic save/load/delete for prospect sessions."""

    @staticmethod
    def save(session_id: str, state: dict) -> bool:
        filepath = _get_safe_path(session_id)
        if filepath is None:
            return False

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(filepath))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
            return True
        except Exception as e:
            logger.error("Failed to save prospect session %s: %s", session_id, e)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        filepath = _get_safe_path(session_id)
        if filepath is None or not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load prospect session %s: %s", session_id, e)
            return None

    @staticmethod
    def delete(session_id: str) -> bool:
        filepath = _get_safe_path(session_id)
        if filepath is None:
            return False

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception as e:
            logger.error("Failed to delete prospect session %s: %s", session_id, e)
            return False
