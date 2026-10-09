"""The review and redo endpoints that make a finished session walkable."""

import pytest

from core.buyer_session import ProviderUnavailable


def test_review_annotates_each_turn_with_its_evidence(sell_client, played_session):
    response = sell_client.get("/api/sell/review", headers=played_session)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert len(payload["turns"]) == 2
    assert payload["turns"][0]["rating"] < payload["turns"][1]["rating"]
    assert "pressure" in payload["turns"][0]["signals"]
    assert payload["turns"][0]["reasons"]
    assert payload["pivotal_turns"] == [1]
    assert payload["persona"]


def test_redo_replaces_the_turn_and_gets_a_real_reply(sell_client, played_session):
    response = sell_client.post(
        "/api/sell/redo",
        json={"turn": 1, "message": "Walk me through what a bad week with the van looks like."},
        headers=played_session,
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["turn"] == 1
    # The AI answer comes first; a scripted objection may follow on some turns.
    assert payload["message"].startswith("Can you tell me a bit more about that?")

    # The pushy turn is gone and the session now holds only the redone one.
    review = sell_client.get("/api/sell/review", headers=played_session).get_json()
    assert len(review["turns"]) == 1
    assert "pressure" not in review["turns"][0]["signals"]
    assert "open_question" in review["turns"][0]["signals"]


@pytest.mark.parametrize("bad_turn", [0, -1, 99, "two", 1.5, True, None])
def test_redo_rejects_a_turn_number_it_cannot_use(sell_client, played_session, bad_turn):
    response = sell_client.post(
        "/api/sell/redo",
        json={"turn": bad_turn, "message": "What matters most to you here?"},
        headers=played_session,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_TURN"


def test_redo_still_validates_the_message(sell_client, played_session):
    response = sell_client.post(
        "/api/sell/redo", json={"turn": 1, "message": ""}, headers=played_session
    )

    assert response.status_code == 400


def test_drills_work_without_any_session(sell_client):
    response = sell_client.get("/api/sell/drills")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["drills"]
    assert all(d["source"] == "authored" for d in payload["drills"])


def test_drills_add_your_own_lines_when_a_session_is_supplied(sell_client, played_session):
    response = sell_client.get("/api/sell/drills", headers=played_session)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["groups"][0]["id"] == "your_own_lines"
    assert payload["drills"][0]["source"] == "own_turn"


def test_drills_ignore_a_session_id_that_is_not_live(sell_client):
    response = sell_client.get("/api/sell/drills", headers={"X-Session-ID": "a" * 32})
    payload = response.get_json()

    assert response.status_code == 200
    assert all(d["source"] == "authored" for d in payload["drills"])


def test_a_bad_session_id_on_drills_is_rejected_not_ignored(sell_client):
    """Silently serving generic drills hides the caller's mistake from them."""
    response = sell_client.get("/api/sell/drills", headers={"X-Session-ID": "not a real id!"})

    assert response.status_code == 400


def test_a_redo_that_cannot_reach_the_buyer_gives_the_turns_back(sell_client, played_session, stub_buyer):
    """The rewind happens before the buyer is asked. If the ask fails, the learner
    must not lose the turns they had and get nothing in return."""
    before = sell_client.get("/api/sell/review", headers=played_session).get_json()

    def dead(*_args, **_kwargs):
        raise ProviderUnavailable("every provider is down")

    stub_buyer.chat = dead
    response = sell_client.post(
        "/api/sell/redo",
        json={"turn": 1, "message": "Walk me through a bad week with the van."},
        headers=played_session,
    )

    assert response.status_code == 503
    after = sell_client.get("/api/sell/review", headers=played_session).get_json()
    assert after["turns"] == before["turns"]


def test_sell_quiz_asks_about_your_own_turn_and_scores_the_answer(sell_client, played_session):
    asked = sell_client.get("/api/sell/quiz", headers=played_session).get_json()

    assert asked["success"] is True
    assert asked["turn"] == 1  # the pushy opener is the weakest turn
    assert "decide right now" in asked["question"]

    scored = sell_client.post(
        "/api/sell/quiz",
        json={"turn": asked["turn"], "answer": "What made that van start to matter so much?"},
        headers=played_session,
    ).get_json()
    assert scored["success"] is True and scored["feedback"].startswith("Better")

    bad = sell_client.post(
        "/api/sell/quiz", json={"turn": 99, "answer": "hello there"}, headers=played_session
    )
    assert bad.status_code == 400
