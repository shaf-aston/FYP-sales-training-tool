"""Session persistence — save/load chatbot state to disk."""

import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = 'sessions'


class SessionPersistence:
    """Handles saving and loading chatbot sessions to/from disk.

    Provides a clean separation between session orchestration (chatbot.py)
    and persistence logic. Sessions are stored as JSON files in sessions/ directory.
    """

    @staticmethod
    def save(
        session_id: str,
        product_type: Optional[str],
        provider_type: Optional[str],
        flow_type: str,
        current_stage: str,
        stage_turn_count: int,
        conversation_history: list[dict[str, str]],
        initial_flow_type: str
    ) -> bool:
        """Save session state to disk.

        Args:
            session_id: Unique session identifier
            product_type: Product context identifier
            provider_type: LLM provider name
            flow_type: Current strategy (consultative/transactional/intent)
            current_stage: Current FSM stage
            stage_turn_count: Number of turns in current stage
            conversation_history: Full message history
            initial_flow_type: Original strategy at session start

        Returns:
            True if save succeeded, False otherwise
        """
        if not session_id:
            return False

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
                "initial_flow_type": initial_flow_type
            }

            filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
            with open(filepath, "w") as f:
                json.dump(state, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
            return False

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """Load session state from disk.

        Args:
            session_id: Unique session identifier

        Returns:
            Dict with session state, or None if not found/failed
        """
        try:
            filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")

            if not os.path.exists(filepath):
                return None

            with open(filepath, "r") as f:
                state = json.load(f)

            return state

        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None

    @staticmethod
    def delete(session_id: str) -> bool:
        """Delete session file from disk.

        Args:
            session_id: Unique session identifier

        Returns:
            True if deletion succeeded, False otherwise
        """
        try:
            filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")

            if os.path.exists(filepath):
                os.remove(filepath)
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    @staticmethod
    def exists(session_id: str) -> bool:
        """Check if session file exists on disk.

        Args:
            session_id: Unique session identifier

        Returns:
            True if session file exists, False otherwise
        """
        filepath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        return os.path.exists(filepath)
