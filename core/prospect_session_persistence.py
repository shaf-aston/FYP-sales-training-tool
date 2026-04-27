"""Prospect session persistence shim.

Prospect conversations now stay in memory and are surfaced through logs only.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ProspectSessionPersistence:
    """Compatibility shim that avoids disk I/O."""

    @staticmethod
    def save(session_id: str, state: dict) -> bool:
        """Log a compact prospect session snapshot instead of writing to disk."""
        logger.info(
            "prospect_session_state %s",
            json.dumps(
                {
                    "session_id": session_id,
                    "difficulty": state.get("difficulty"),
                    "product_type": state.get("product_type"),
                    "turn_count": state.get("state", {}).get("turn_count"),
                    "message_count": len(state.get("conversation_history", []) or []),
                    "persona_name": (state.get("persona") or {}).get("name", "Unknown"),
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        return True

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """Return None because prospect session disk recovery is disabled."""
        logger.debug("prospect_session_load_disabled session_id=%s", session_id)
        return None

    @staticmethod
    def delete(session_id: str) -> bool:
        """Acknowledge delete requests without touching disk state."""
        logger.info("prospect_session_delete_disabled session_id=%s", session_id)
        return True
