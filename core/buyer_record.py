"""What a sell session writes down: its saved snapshot, log line and analytics events."""

import json
import logging

from .analytics.session_analytics import SessionAnalytics

logger = logging.getLogger(__name__)


class SessionRecord:
    """Mixin for BuyerSession. Reads session_id, state, conversation_history, persona,
    product_type and provider_name from the session it is mixed into."""

    def to_dict(self) -> dict:
        """Serialize enough state to recover the session after a reload."""
        return {
            "session_id": self.session_id,
            "provider_type": self.provider_name,
            "product_type": self.product_type,
            "difficulty": self.state.difficulty,
            "persona": self.persona,
            "conversation_history": self.conversation_history,
            "state": {
                "readiness": self.state.readiness,
                "turn_count": self.state.turn_count,
                "has_committed": self.state.has_committed,
                "has_walked": self.state.has_walked,
            },
        }

    def save_session(self) -> None:
        """Log a compact snapshot of the sell session."""
        if not self.session_id:
            return
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

    def _log_turn_event(
        self, user_message: str | None, assistant_message: str, turn_index: int
    ) -> None:
        """Record the full sell-mode exchange as an analytics event."""

        if not self.session_id:
            return

        SessionAnalytics.record(
            session_id=self.session_id,
            event="sell_conversation_turn",
            turn_index=turn_index,
            difficulty=self.state.difficulty,
            product_type=self.product_type,
            current_readiness=round(self.state.readiness, 3),
            user_message=user_message,
            assistant_message=assistant_message,
            persona_name=self.persona.get("name", "Alex"),
        )

    def record_session_end(self) -> None:
        """Record where this session actually got to.

        Sessions were counted at the start and never at the end, so there was no
        way to tell whether anyone finished one, let alone improved.
        """
        if not self.session_id:
            return
        SessionAnalytics.record(
            session_id=self.session_id,
            event="session_end",
            engine="sell",
            outcome=self.state.status,
            difficulty=self.state.difficulty,
            product_type=self.product_type,
            turn_count=self.state.turn_count,
            objections_raised=self.state.objections_raised,
            final_readiness=round(self.state.readiness, 3),
        )
