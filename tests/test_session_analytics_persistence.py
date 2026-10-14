"""Session analytics: every event is logged, and appended to a JSONL file when one is configured."""
import logging

from core.analytics.session_analytics import SessionAnalytics


def test_an_event_is_logged(caplog):
    caplog.set_level(logging.INFO)

    SessionAnalytics.record(event="session_start", session_id="session123", product_type="default")

    assert any("session_analytics" in r.message and "session123" in r.message for r in caplog.records)


def test_events_are_appended_to_the_jsonl_file_when_configured(analytics_events):
    SessionAnalytics.record(event="session_start", session_id="alpha", product_type="default")
    SessionAnalytics.record(event="session_end", session_id="alpha", turn_count=2)
    SessionAnalytics.record(event="session_start", session_id="beta")

    assert [e["event_type"] for e in analytics_events("alpha")] == ["session_start", "session_end"]
    assert analytics_events("alpha", "session_end")[0]["turn_count"] == 2
    assert len(analytics_events("beta")) == 1


def test_no_file_is_written_unless_configured(tmp_path, monkeypatch):
    monkeypatch.delenv("METRICS_JSONL_PATH", raising=False)
    monkeypatch.chdir(tmp_path)

    SessionAnalytics.record(event="session_start", session_id="alpha")

    assert list(tmp_path.iterdir()) == []


def test_an_event_without_a_session_is_ignored(analytics_events, caplog):
    caplog.set_level(logging.INFO)

    SessionAnalytics.record(event="session_start", session_id="")

    assert not any("session_analytics" in r.message for r in caplog.records)
