"""What a sell session writes down: its log line and analytics events."""

import json
import logging

from .analytics.session_analytics import SessionAnalytics
from .buyer_state import persona_name

logger = logging.getLogger(__name__)


class BuyerRecord:
    """Mixin for BuyerSession. Reads session_id, state, conversation_history, persona
    and product_type from the session it is mixed into."""

    def log_snapshot(self) -> None:
        """Write the session's current state to the log for monitoring (nothing is stored)."""
        logger.info(
            "buyer_session_state %s",
            json.dumps(
                {
                    "session_id": self.session_id,
                    "difficulty": self.state.difficulty,
                    "turn_count": self.state.turn_count,
                    "message_count": len(self.conversation_history),
                },
                ensure_ascii=False,
            ),
        )

    def _log_turn_event(self, user_message: str | None, assistant_message: str, turn_index: int) -> None:
        """Record the full sell-mode exchange as an analytics event."""
        SessionAnalytics.record(
            session_id=self.session_id,
            event="conversation_turn",
            mode="sell",
            turn_index=turn_index,
            difficulty=self.state.difficulty,
            product_type=self.product_type,
            current_readiness=round(self.state.readiness, 3),
            user_message=user_message,
            assistant_message=assistant_message,
            persona_name=persona_name(self.persona),
        )

    def record_session_end(self) -> None:
        """Record where this session got to, so finished sessions can be counted against started ones."""
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_end",
            mode="sell",
            outcome=self.state.status,
            difficulty=self.state.difficulty,
            product_type=self.product_type,
            turn_count=self.state.turn_count,
            objections_raised=self.state.objections_raised,
            final_readiness=round(self.state.readiness, 3),
        )
