"""Persist chatbot session state to disk atomically (safe, simple, reliable).

Core idea: Write to temp file first, then rename (atomic operation). If crash
happens mid-write, the original file is untouched. Validates paths to prevent
directory escape attacks (../../../etc/passwd).
"""

import json
import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Absolute path: core/.. = repo root, then /sessions
SESSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sessions"))
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _is_valid_session_id(session_id: str) -> bool:
    """Reject invalid characters (only allow alphanumeric, underscore, hyphen)."""
    if not isinstance(session_id, str) or not session_id:
        return False
    return bool(re.match(r"^[A-Za-z0-9_-]+$", session_id))


def _get_safe_path(session_id: str) -> Optional[str]:
    """Build safe absolute filepath. Returns None if path traversal detected."""
    if not _is_valid_session_id(session_id):
        logger.warning("Rejected invalid session_id: %r", session_id)
        return None

    filepath = os.path.abspath(os.path.join(SESSIONS_DIR, f"{session_id}.json"))
    # Ensure filepath is inside SESSIONS_DIR (prevents ../../../etc/passwd attacks)
    if not filepath.startswith(os.path.abspath(SESSIONS_DIR) + os.sep):
        logger.warning("Blocked path traversal attempt: %r", filepath)
        return None

    return filepath


class SessionPersistence:
    """Minimal atomic writer for session state with per-turn snapshots."""

    @staticmethod
    def save(session_id: str, product_type: Optional[str], provider_type: Optional[str],
             flow_type: str, current_stage: str, stage_turn_count: int,
             conversation_history: list[dict[str, str]], initial_flow_type: str,
             turn_snapshots: Optional[list[dict]] = None) -> bool:
        """Write session state atomically to disk. Returns True on success."""
        filepath = _get_safe_path(session_id)
        if filepath is None:
            return False

        state = {
            "session_id": session_id,
            "product_type": product_type,
            "provider_type": provider_type,
            "flow_type": flow_type,
            "current_stage": current_stage,
            "stage_turn_count": stage_turn_count,
            "conversation_history": conversation_history,
            "initial_flow_type": initial_flow_type,
            "turn_snapshots": turn_snapshots or [],
        }

        tmp_path = None
        try:
            # Write to temp file first
            fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(filepath))
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Force to disk
            # Atomic rename (overwrites destination if exists)
            os.replace(tmp_path, filepath)
            return True
        except Exception as e:
            logger.error("Failed to save session %s: %s", session_id, e)
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """Read session state from disk. Returns None if missing or corrupted."""
        filepath = _get_safe_path(session_id)
        if filepath is None:
            return None

        try:
            if not os.path.exists(filepath):
                return None
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load session %s: %s", session_id, e)
            return None
