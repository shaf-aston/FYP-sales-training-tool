"""Tests for log-only session analytics storage."""
import logging

from core.analytics.session_analytics import SessionAnalytics


def _reset_analytics_cache():
    SessionAnalytics._events.clear()


def test_session_analytics_stays_in_memory_and_logs(caplog):
    _reset_analytics_cache()
    caplog.set_level(logging.INFO)

    SessionAnalytics.record_session_start(
        "session123",
        product_type="default",
        initial_strategy="intent",
        ab_variant="A",
    )
    SessionAnalytics.record_stage_transition(
        "session123",
        from_stage="intent",
        to_stage="logical",
        strategy="consultative",
        user_turns_in_stage=2,
    )

    assert [event["event_type"] for event in SessionAnalytics.get_session_analytics("session123")] == [
        "session_start",
        "stage_transition",
    ]
    assert any("session_analytics" in record.message for record in caplog.records)


def test_session_analytics_summary_reads_in_memory_events(caplog):
    _reset_analytics_cache()
    caplog.set_level(logging.INFO)

    SessionAnalytics.record_session_start("alpha", product_type="default", initial_strategy="intent")
    SessionAnalytics.record_stage_transition(
        "alpha",
        from_stage="intent",
        to_stage="logical",
        strategy="consultative",
        user_turns_in_stage=1,
    )
    SessionAnalytics.record_session_start("beta", product_type="default", initial_strategy="intent")

    summary = SessionAnalytics.get_evaluation_summary()

    assert summary["total_sessions"] == 2
    assert summary["total_events"] == 3
    assert summary["event_counts"] == {
        "session_start": 2,
        "stage_transition": 1,
    }
    assert any("session_analytics" in record.message for record in caplog.records)
