"""Session persistence shim.

Conversation state is no longer written to disk. The app keeps state in memory
for the lifetime of the process and emits log events for monitoring.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SessionPersistence:
    """Compatibility shim that logs state instead of writing files."""

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
        turn_snapshots: Optional[list[dict]] = None,
    ) -> bool:
        """Log the current session state and report success.

        The implementation stays side-effect free so Render logs are the only
        durable monitoring surface.
        """

        logger.info(
            "session_state %s",
            json.dumps(
                {
                    "session_id": session_id,
                    "product_type": product_type,
                    "provider_type": provider_type,
                    "flow_type": flow_type,
                    "current_stage": current_stage,
                    "stage_turn_count": stage_turn_count,
                    "initial_flow_type": initial_flow_type,
                    "turn_count": len(conversation_history) // 2,
                    "message_count": len(conversation_history),
                    "turn_snapshot_count": len(turn_snapshots or []),
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        return True

    @staticmethod
    def load(session_id: str) -> Optional[dict]:
        """Loading from disk is disabled."""

        logger.debug("session_load_disabled session_id=%s", session_id)
        return None
