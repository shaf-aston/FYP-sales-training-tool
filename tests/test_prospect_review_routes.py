"""The review and redo endpoints that make a finished session walkable."""

import pytest

from backend.app import app
from core.providers.base import LLMResponse


class StubProspectProvider:
    provider_name = "stub"

    def get_model_name(self):
        return "stub-model"

    def chat(self, messages, temperature=0.7, max_tokens=150):
        last_message = messages[-1]["content"]
        if "Start the conversation naturally" in last_message:
            return LLMResponse(content="My old van keeps breaking down on me.")
        return LLMResponse(content="Can you tell me a bit more about that?")


@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    monkeypatch.setattr(
        "core.prospect_session.create_provider",
        lambda *_args, **_kwargs: StubProspectProvider(),
    )
    return app.test_client()


@pytest.fixture
def played_session(client):
    """A session with a pushy turn and a good one, so a review has something to say."""
    started = client.post(
        "/api/prospect/init", json={"difficulty": "medium", "product_type": "default"}
    ).get_json()
    headers = {"X-Session-ID": started["session_id"]}

    for message in (
        "You need to decide right now, today only.",
        "What made the reliability of your van start to matter so much?",
    ):
        client.post("/api/prospect/chat", json={"message": message}, headers=headers)
    return headers


def test_review_annotates_each_turn_with_its_evidence(client, played_session):
    response = client.get("/api/prospect/review", headers=played_session)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert len(payload["turns"]) == 2
    assert payload["turns"][0]["rating"] < payload["turns"][1]["rating"]
    assert "pressure" in payload["turns"][0]["signals"]
    assert payload["turns"][0]["reasons"]
    assert payload["pivotal_turns"] == [1]
    assert payload["persona"]


def test_review_needs_a_live_session(client):
    response = client.get("/api/prospect/review", headers={"X-Session-ID": "a" * 32})

    assert response.status_code == 400
    assert response.get_json()["code"] == "SESSION_EXPIRED"


def test_redo_replaces_the_turn_and_gets_a_real_reply(client, played_session):
    response = client.post(
        "/api/prospect/redo",
        json={"turn": 1, "message": "Walk me through what a bad week with the van looks like."},
        headers=played_session,
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["turn"] == 1
    assert payload["message"] == "Can you tell me a bit more about that?"

    # The pushy turn is gone and the session now holds only the redone one.
    review = client.get("/api/prospect/review", headers=played_session).get_json()
    assert len(review["turns"]) == 1
    assert "pressure" not in review["turns"][0]["signals"]
    assert review["turns"][0]["rating"] > 3


@pytest.mark.parametrize("bad_turn", [0, -1, 99, "two", 1.5, True, None])
def test_redo_rejects_a_turn_number_it_cannot_use(client, played_session, bad_turn):
    response = client.post(
        "/api/prospect/redo",
        json={"turn": bad_turn, "message": "What matters most to you here?"},
        headers=played_session,
    )

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_TURN"


def test_redo_still_validates_the_message(client, played_session):
    response = client.post(
        "/api/prospect/redo", json={"turn": 1, "message": ""}, headers=played_session
    )

    assert response.status_code == 400


def test_drills_work_without_any_session(client):
    response = client.get("/api/prospect/drills")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["drills"]
    assert all(d["source"] == "authored" for d in payload["drills"])


def test_drills_add_your_own_lines_when_a_session_is_supplied(client, played_session):
    response = client.get("/api/prospect/drills", headers=played_session)
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["groups"][0]["id"] == "your_own_lines"
    assert payload["drills"][0]["source"] == "own_turn"


def test_drills_ignore_a_session_id_that_is_not_live(client):
    response = client.get("/api/prospect/drills", headers={"X-Session-ID": "a" * 32})
    payload = response.get_json()

    assert response.status_code == 200
    assert all(d["source"] == "authored" for d in payload["drills"])
