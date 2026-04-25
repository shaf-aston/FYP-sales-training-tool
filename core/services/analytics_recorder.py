"""Analytics adapter to reduce tight coupling in SalesChatbot."""

from __future__ import annotations

from ..analytics.performance import PerformanceTracker
from ..analytics.session_analytics import SessionAnalytics


class AnalyticsRecorder:
    def record_session_start(
        self,
        *,
        session_id: str,
        product_type: str,
        initial_strategy: str,
        ab_variant: str | None,
    ) -> None:
        SessionAnalytics.record_session_start(
            session_id=session_id,
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
        SessionAnalytics.record_intent_classification(
            session_id=session_id,
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
        SessionAnalytics.record_stage_transition(
            session_id=session_id,
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
        SessionAnalytics.record_strategy_switch(
            session_id=session_id,
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
        SessionAnalytics.record_objection_classified(
            session_id=session_id,
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
