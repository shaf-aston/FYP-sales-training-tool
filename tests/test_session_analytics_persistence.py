"""Tests for durable session analytics storage."""

import json
from pathlib import Path

from core.analytics.session_analytics import SessionAnalytics


def _reset_analytics_cache():
    SessionAnalytics._events.clear()


def test_session_analytics_persists_to_jsonl_and_survives_cache_clear(monkeypatch):
    temp_dir = Path.cwd() / ".tmp" / "analytics-persistence"
    sessions_dir = temp_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("core.analytics.session_analytics.SESSION_EVENTS_DIR", str(sessions_dir))
    _reset_analytics_cache()
    analytics_file = sessions_dir / "session123.jsonl"
    if analytics_file.exists():
        analytics_file.unlink()

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

    assert analytics_file.exists()
    lines = analytics_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event_type"] == "session_start"

    _reset_analytics_cache()
    events = SessionAnalytics.get_session_analytics("session123")

    assert [event["event_type"] for event in events] == [
        "session_start",
        "stage_transition",
    ]


def test_session_analytics_summary_reads_persisted_events(monkeypatch):
    temp_dir = Path.cwd() / ".tmp" / "analytics-summary"
    sessions_dir = temp_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("core.analytics.session_analytics.SESSION_EVENTS_DIR", str(sessions_dir))
    _reset_analytics_cache()
    for path in sessions_dir.glob("*.jsonl"):
        path.unlink()

    SessionAnalytics.record_session_start("alpha", product_type="default", initial_strategy="intent")
    SessionAnalytics.record_stage_transition(
        "alpha",
        from_stage="intent",
        to_stage="logical",
        strategy="consultative",
        user_turns_in_stage=1,
    )
    SessionAnalytics.record_session_start("beta", product_type="default", initial_strategy="intent")

    _reset_analytics_cache()
    summary = SessionAnalytics.get_evaluation_summary()

    assert summary["total_sessions"] == 2
    assert summary["total_events"] == 3
    assert summary["event_counts"] == {
        "session_start": 2,
        "stage_transition": 1,
    }
