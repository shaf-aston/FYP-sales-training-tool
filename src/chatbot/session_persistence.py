"""Save and load chatbot session state to disk"""

import json
import logging
import os
import re
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sessions"))


def _is_valid_session_id(session_id: str) -> bool:
    """check session id format"""
    if not isinstance(session_id, str) or not session_id:
        return False
    return bool(re.match(r"^[A-Za-z0-9_-]+$", session_id))


def _session_filepath(session_id: str) -> Optional[str]:
    """build a safe absolute filepath for a session id"""
    if not _is_valid_session_id(session_id):
        logger.warning("Rejected invalid session_id: %r", session_id)
        return None

    filepath = os.path.abspath(os.path.join(SESSIONS_DIR, f"{session_id}.json"))

    safe_prefix = os.path.abspath(SESSIONS_DIR) + os.sep
    if not filepath.startswith(safe_prefix):
        logger.warning("Blocked session path: %r", filepath)
        return None

    return filepath


class SessionPersistence:
    """persist chatbot sessions as json files"""

    @staticmethod
    def save(
        session_id: str,
        product_type: Optional[str],
        provider_type: Optional[str],
        flow_type: str,
        current_stage: str,
        stage_turn_count: int,
        conversation_history: list[dict[str, str]],
        initial_flow_type: str,
    ) -> bool:
        """write session state to disk"""
        filepath = _session_filepath(session_id)
        if filepath is None:
            return False

        tmp_path = None
        try:
            os.makedirs(SESSIONS_DIR, exist_ok=True)

            state = {
                "session_id": session_id,
                "product_type": product_type,
                "provider_type": provider_type,
                "flow_type": flow_type,
                "current_stage": current_stage,
                "stage_turn_count": stage_turn_count,
                "conversation_history": conversation_history,
                "initial_flow_type": initial_flow_type,
            }

            # atomic write
            dirpath = os.path.dirname(filepath)
            fd, tmp_path = tempfile.mkstemp(prefix=session_id + ".", dir=dirpath)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, filepath)
            return True

        except Exception as e:
            logger.error("Failed to save session %s: %s", session_id, e)
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            return False

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """read session state from disk"""
        filepath = _session_filepath(session_id)
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

