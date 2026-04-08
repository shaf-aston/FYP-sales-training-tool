import pytest
from chatbot.analytics.session_analytics import SessionAnalytics


def test_sanitize_large_and_non_numeric():
    events = [
        {"event_type": "stage_transition", "user_turns_in_stage": "10000000"},
        {"event_type": "intent_classification", "user_turn": "N/A"},
        {"event_type": "session_end", "user_turn_count": "5"},
    ]

    s = SessionAnalytics.sanitize_events(events)
    # large value capped to ABSOLUTE_CAP (10000)
    assert s[0]["user_turns_in_stage"] == 10000
    # non-numeric becomes None
    assert s[1]["user_turn"] is None
    # numeric string coerced to int
    assert s[2]["user_turn_count"] == 5
