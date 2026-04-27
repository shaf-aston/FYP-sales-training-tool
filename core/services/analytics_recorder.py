"""Analytics adapter used by `SalesChatbot`.

This is intentionally thin: it keeps `SalesChatbot` readable while ensuring
analytics is a simple one-liner at each call site.
"""

from __future__ import annotations

from ..analytics.performance import PerformanceTracker
from ..analytics.session_analytics import SessionAnalytics


class AnalyticsRecorder:
    def record(self, *, session_id: str, event: str, **payload) -> None:
        """Forward one generic analytics event to the shared session store."""
        SessionAnalytics.record(session_id=session_id, event=event, **payload)

    def record_session_start(
        self,
        *,
        session_id: str,
        product_type: str,
        initial_strategy: str,
        ab_variant: str | None,
    ) -> None:
        """Record the first event for a newly created chatbot session."""
        self.record(
            session_id=session_id,
            event="session_start",
            product_type=product_type,
            initial_strategy=initial_strategy,
            ab_variant=ab_variant,
        )

    def record_intent_classification(
        self,
        *,
        session_id: str,
        intent_level,
        user_turn_count: int,
    ) -> None:
        """Record the latest intent classification for the current turn."""
        self.record(
            session_id=session_id,
            event="intent_classification",
            intent_level=intent_level,
            user_turn_count=user_turn_count,
        )

    def record_stage_transition(
        self,
        *,
        session_id: str,
        from_stage: str,
        to_stage: str,
        strategy: str,
        user_turns_in_stage: int,
    ) -> None:
        """Record a stage transition inside the conversation flow."""
        self.record(
            session_id=session_id,
            event="stage_transition",
            from_stage=from_stage,
            to_stage=to_stage,
            strategy=strategy,
            user_turns_in_stage=user_turns_in_stage,
        )

    def record_strategy_switch(
        self,
        *,
        session_id: str,
        from_strategy: str,
        to_strategy: str,
        reason: str,
        user_turn_count: int,
    ) -> None:
        """Record when the chatbot switches between strategies."""
        self.record(
            session_id=session_id,
            event="strategy_switch",
            from_strategy=from_strategy,
            to_strategy=to_strategy,
            reason=reason,
            user_turn_count=user_turn_count,
        )

    def record_objection_classified(
        self,
        *,
        session_id: str,
        objection_type: str,
        strategy: str,
        user_turn_count: int,
    ) -> None:
        """Record which objection type was classified for the user turn."""
        self.record(
            session_id=session_id,
            event="objection_classified",
            objection_type=objection_type,
            strategy=strategy,
            user_turn_count=user_turn_count,
        )

    def log_stage_latency(
        self,
        *,
        session_id: str,
        stage,
        strategy,
        latency_ms: float | None,
        provider: str,
        model: str,
        user_message_length: int,
        bot_response_length: int,
    ) -> None:
        """Record latency metrics for the completed stage response."""
        PerformanceTracker.log_stage_latency(
            session_id=session_id,
            stage=stage,
            strategy=strategy,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            user_message_length=user_message_length,
            bot_response_length=bot_response_length,
        )
