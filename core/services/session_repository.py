"""Session persistence adapter for SalesChatbot."""

from __future__ import annotations

from ..session_persistence import SessionPersistence


class SessionRepository:
    def save_chatbot_state(
        self,
        *,
        session_id: str,
        product_type: str | None,
        provider_type: str | None,
        flow_type,
        current_stage,
        stage_turn_count: int,
        conversation_history: list,
        initial_flow_type,
        turn_snapshots: list,
    ) -> bool:
        return bool(
            SessionPersistence.save(
                session_id=session_id,
                product_type=product_type,
                provider_type=provider_type,
                flow_type=flow_type,
                current_stage=current_stage,
                stage_turn_count=stage_turn_count,
                conversation_history=conversation_history,
                initial_flow_type=initial_flow_type,
                turn_snapshots=turn_snapshots,
            )
        )

    def load_chatbot_state(self, session_id: str) -> dict | None:
        return SessionPersistence.load(session_id)

