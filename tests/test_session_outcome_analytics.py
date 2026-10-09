"""Sessions are counted at the start, at the end and when scored, so finished sessions
can be compared with started ones."""

from core.analytics.session_analytics import SessionAnalytics


def events_for(session_id, event):
    return [
        e
        for e in SessionAnalytics.get_session_analytics(session_id)
        if e.get("event_type") == event
    ]


def test_ending_a_sell_session_is_recorded(sell_client, played_session):
    session_id = played_session["X-Session-ID"]

    sell_client.post("/api/sell/reset", headers=played_session)

    ended = events_for(session_id, "session_end")
    assert len(ended) == 1
    assert ended[0]["mode"] == "sell"
    assert ended[0]["outcome"] in {"active", "sold", "walked"}
    assert ended[0]["turn_count"] == 2
    assert "final_readiness" in ended[0]


def test_a_sell_session_is_counted_at_the_start_too(sell_client, played_session):
    """Ends are only meaningful next to starts from the same mode."""
    started = events_for(played_session["X-Session-ID"], "session_start")

    assert len(started) == 1
    assert started[0]["mode"] == "sell"
    assert started[0]["difficulty"] == "medium"


def test_a_sell_score_is_kept_not_just_shown(sell_client, played_session):
    session_id = played_session["X-Session-ID"]

    response = sell_client.post("/api/sell/evaluate", headers=played_session)

    assert response.status_code == 200
    scored = events_for(session_id, "session_score")
    assert len(scored) == 1
    assert isinstance(scored[0]["total"], int)
    assert scored[0]["breakdown"]
    assert scored[0]["mode"] == "sell"


def test_resetting_a_session_that_is_already_gone_records_nothing(sell_client):
    """A stale id must not invent an ending for a session nobody played."""
    ghost = "b" * 32

    response = sell_client.post("/api/sell/reset", headers={"X-Session-ID": ghost})

    assert response.status_code == 200
    assert events_for(ghost, "session_end") == []


def test_ending_a_buy_session_records_where_it_got_to():
    """Ending a session records the final stage reached."""
    from core.seller_bot import SellerBot

    class _Call:
        current_stage = "pitch"
        strategy = "consultative"
        user_turn_count = 4
        conversation_history = [{"role": "user"}, {"role": "assistant"}]

    seller = SellerBot.__new__(SellerBot)
    seller.session_id = "c" * 32
    seller.call = _Call()
    seller.record_session_end()

    ended = events_for(seller.session_id, "session_end")
    assert len(ended) == 1
    assert ended[0]["final_stage"] == "pitch"
    assert ended[0]["mode"] == "buy"
    assert ended[0]["turn_count"] == 4


def test_a_buy_session_with_no_id_records_nothing():
    from core.seller_bot import SellerBot

    seller = SellerBot.__new__(SellerBot)
    seller.session_id = ""

    seller.record_session_end()  # must not raise

    assert events_for("", "session_end") == []
