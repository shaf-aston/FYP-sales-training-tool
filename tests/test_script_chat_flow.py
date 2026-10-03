"""Slice 5: a scripted call through /api/init, /api/chat and /api/edit (offline provider)."""
import pytest

from backend.app import app

CONSULTATIVE_PRODUCT = "luxury_cars"


@pytest.fixture
def client(scripted_selling, monkeypatch):
    # the route only lists real providers; the offline test provider is let through here
    monkeypatch.setattr("backend.routes.session.validate_provider", lambda data: ("dummy", None))
    app.config["TESTING"] = True
    return app.test_client()


def _init(client):
    response = client.post(
        "/api/init", json={"product_type": CONSULTATIVE_PRODUCT}
    )
    body = response.get_json()
    assert response.status_code == 200, body
    return body, {"X-Session-ID": body["session_id"]}


def _say(client, headers, text):
    response = client.post("/api/chat", json={"message": text}, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_call_opens_with_the_script_and_follows_it(client):
    opened, headers = _init(client)
    assert opened["message"].endswith("I don't like to assume anything.")  # plain line: no setter
    assert "{" not in opened["message"]

    # step 00 listens for anything; the next line is step 01's question
    asked = _say(client, headers, "ok")
    assert asked["message"].startswith("What do you want to specifically achieve")
    # "freedom" is recognised, so the script moves to step 02. The dummy provider's blank
    # filler breaks the checks, so the plain script line is said.
    assert _say(client, headers, "I want financial freedom")["message"] == (
        "How much do you need to be making to feel that freedom?"
    )
    plain = _say(client, headers, "ten thousand a month")["message"]
    assert plain == "How long have you been thinking about this?"


def test_stage_comes_from_the_script_step(client):
    _, headers = _init(client)
    reply = _say(client, headers, "I want to be free from my 9-5 and work from anywhere")
    assert reply["stage"].lower() == "logical"


def test_same_replies_give_the_same_call(client):
    def call():
        opened, headers = _init(client)
        lines = [opened["message"]]
        for text in ("I want financial freedom", "ten thousand a month", "three years"):
            lines.append(_say(client, headers, text)["message"])
        return lines

    assert call() == call()


def test_edit_rewinds_the_script_too(client):
    _, headers = _init(client)
    first = _say(client, headers, "I want financial freedom")["message"]
    _say(client, headers, "ten thousand a month")
    edited = client.post(
        "/api/edit", json={"index": 1, "message": "I want financial freedom"}, headers=headers
    ).get_json()
    assert edited["message"] == first
    assert edited["history"][0]["content"] == "I want financial freedom"
