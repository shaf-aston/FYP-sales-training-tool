"""/api/calls (read and review an uploaded call) and practising against it through /api/sell/init."""
import pytest

from core.infra.loader import CONFIG_DIR

SAMPLE = (CONFIG_DIR / "calls_sample.txt").read_text("utf-8")


def test_sample_is_a_readable_call(client):
    body = client.get("/api/calls/sample").get_json()
    assert body["text"] == SAMPLE
    assert client.post("/api/calls/read", json={"text": body["text"]}).status_code == 200


def test_read_returns_speakers_roles_turns_and_profile(client):
    body = client.post("/api/calls/read", json={"text": SAMPLE}).get_json()
    assert body["format"] == "speaker_blocks"
    assert [s["name"] for s in body["speakers"]] == ["Sarah Khan", "Dan Price"]
    assert body["rep"] == {"name": "Sarah Khan", "how": "most_questions", "sure": True}
    assert body["prospect"] == "Dan Price"
    assert body["turns"][0] == {"speaker": "Sarah Khan", "role": "rep", "text": body["turns"][0]["text"], "at": "0:02"}
    assert set(body["profile"]) == {"name", "background", "personality", "budget", "needs", "pain_points",
                                    "objections", "difficulty", "evidence"}


def test_naming_the_rep_swaps_the_sides(client):
    body = client.post("/api/calls/read", json={"text": SAMPLE, "rep": "Dan Price"}).get_json()
    assert body["prospect"] == "Sarah Khan" and body["profile"]["name"] == "Sarah"


@pytest.mark.parametrize("payload, code", [
    ({}, "CALL_UNREADABLE"),
    ({"text": "   "}, "CALL_UNREADABLE"),
    ({"text": "no speakers here"}, "CALL_UNREADABLE"),
    ({"text": SAMPLE, "rep": "Nobody"}, "UNKNOWN_SPEAKER"),
])
def test_bad_input_says_what_to_do(client, payload, code):
    response = client.post("/api/calls/read", json=payload)
    assert response.status_code == 400
    assert response.get_json()["code"] == code and response.get_json()["error"]


def test_a_huge_request_is_refused_before_it_is_read(client):
    response = client.post("/api/calls/read", data="x" * 2_000_000, content_type="application/json")
    assert response.status_code == 413


def test_review_rates_the_reps_lines_like_a_practice_session(client):
    body = client.post("/api/calls/review", json={"text": SAMPLE}).get_json()
    assert set(body) >= {"turns", "pivotal_turns", "summary", "readiness_curve"}
    assert "readiness_exact" not in body
    assert body["turns"][0]["seller"].startswith("Hi Dan")
    assert body["turns"][0]["buyer"].startswith("Yeah, no worries")
    assert body["summary"]["turn_count"] == len(body["turns"]) == 10


def test_review_refuses_an_unknown_difficulty(client):
    response = client.post("/api/calls/review", json={"text": SAMPLE, "difficulty": "brutal"})
    assert response.status_code == 400


def test_practise_against_the_prospect_from_the_call(sell_client):
    profile = sell_client.post("/api/calls/read", json={"text": SAMPLE}).get_json()["profile"]
    custom = {k: profile[k] for k in ("name", "background", "personality", "budget", "needs", "pain_points", "objections")}
    started = sell_client.post("/api/sell/init", json={
        "product_type": "default", "difficulty": profile["difficulty"], "custom_buyer": custom,
    })
    body = started.get_json()
    assert started.status_code == 200, body
    assert body["persona"]["name"] == "Dan"
    assert body["persona"]["background"] == "I run a small marketing agency, about six of us."
    assert body["message"] == "Hi, Dan here. I've got about twenty minutes. What did you want to cover?"


@pytest.mark.parametrize("custom, detail", [
    ("Dan", "custom_buyer"),
    ({"background": "no name"}, "name"),
    ({"name": "Dan", "needs": "one string"}, "needs"),
    ({"name": "Dan", "objections": [{"type": "anger", "text": "No."}]}, "objections"),
    ({"name": "x" * 301}, "name"),
])
def test_a_malformed_custom_buyer_is_refused(sell_client, custom, detail):
    response = sell_client.post("/api/sell/init", json={"product_type": "default", "custom_buyer": custom})
    assert response.status_code == 400
    assert detail in response.get_json()["error"]


def test_the_custom_buyer_raises_its_own_objections_first(monkeypatch):
    from core.sell_mode.buyer_session import BuyerSession

    bank = [{"type": "price", "text": "That's more than I budgeted for."}]
    session = BuyerSession(provider_type=None, difficulty="hard", persona={"name": "Dan", "custom": True},
                           session_id="test-session-1234", objection_bank=bank)
    assert session.pacer.bank == bank
