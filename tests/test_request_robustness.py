"""Odd requests get a clear 4xx in JSON, never a 500; one call's requests take turns (live audit, 12 Nov)."""

import threading
import time

import pytest

from backend.app import app
from core.infra.providers.base import LLMResponse


@pytest.fixture
def c(stub_buyer, monkeypatch):
    monkeypatch.setattr("backend.routes.buy.validate_provider", lambda data: ("dummy", None))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize("path", ["/api/sell/init", "/api/buy/init", "/api/feedback"])
@pytest.mark.parametrize("body", [[1], "str", 5])
def test_a_body_that_is_not_an_object_is_not_a_500(c, path, body):
    assert c.post(path, json=body).status_code < 500


def test_wrong_types_and_huge_numbers_are_4xx(c):
    sell = c.post("/api/sell/init", json={"difficulty": "easy", "product_type": {"a": 1}})
    assert sell.status_code == 400
    buy = c.post("/api/buy/init", json={"product_type": {"a": 1}}).get_json()   # falls back to the default product
    headers = {"X-Session-ID": buy["session_id"]}
    for path, body in [("/api/buy/coach", {"question": 123}), ("/api/buy/coach", {"question": "Why?", "style": 5}),
                       ("/api/buy/quiz/stage", {"answer": 5}), ("/api/buy/quiz/next-move", {"response": ["a"]}),
                       ("/api/buy/edit", {"index": 1e400, "message": "hi"})]:
        assert c.post(path, json=body, headers=headers).status_code < 500, (path, body)
    assert c.post("/api/feedback", json={"rating": 1e400}).status_code == 400


def test_an_id_too_big_to_store_is_a_400(c):
    c.post("/api/account/signup", json={"email": "big@x.co", "name": "Big", "password": "longenough"})
    res = c.delete("/api/account/prospects/99999999999999999999999")
    assert res.status_code == 400 and res.get_json()["code"] == "NUMBER_TOO_BIG"
    assert c.post("/api/team/remove", json={"user_id": 99999999999999999999999}).status_code < 500


def test_api_errors_are_json_without_the_parsers_detail(c):
    bad = c.post("/api/sell/chat", data="{not json", content_type="application/json", headers={"X-Session-ID": "a" * 32})
    assert bad.is_json
    missing = c.get("/api/no-such-thing")
    assert missing.status_code == 404 and missing.is_json and missing.get_json()["code"] == "NOT_FOUND"
    wrong = c.delete("/api/sell/init")
    assert wrong.status_code == 405 and wrong.is_json
    assert "Expecting" not in bad.get_data(as_text=True)


def test_a_manager_removing_themselves_is_told_to_leave(c):
    c.post("/api/account/signup", json={"email": "boss@x.co", "name": "Boss", "password": "longenough"})
    me = c.post("/api/team/create", json={"name": "Crew"}).get_json()
    uid = c.get("/api/account/me").get_json()["user"]["id"]
    res = c.post("/api/team/remove", json={"user_id": uid})
    assert res.status_code == 400 and res.get_json()["code"] == "REMOVE_SELF" and me["success"]


def test_two_sends_at_once_on_one_call_take_turns(c, stub_buyer, monkeypatch):
    """A duplicated tab sent two lines at once: two seller lines in a row, then two replies."""
    monkeypatch.setattr("core.sell_mode.buyer_session.LINE_BANK", False)   # every reply goes to the (slow) AI
    stub_buyer.chat = lambda messages, **kw: (time.sleep(0.2), LLMResponse(content="Go on."))[1]
    sid = c.post("/api/sell/init", json={"difficulty": "medium"}).get_json()["session_id"]
    headers = {"X-Session-ID": sid}
    results = []

    def send(text):
        results.append(app.test_client().post("/api/sell/chat", json={"message": text}, headers=headers).status_code)

    threads = [threading.Thread(target=send, args=(t,)) for t in ("What brought you here today?", "What matters most?")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    history = c.get("/api/sell/state", headers=headers).get_json()["history"]
    roles = [m["role"] for m in history]
    assert results == [200, 200]
    assert all(a != b for a, b in zip(roles, roles[1:])), roles   # seller and buyer alternate
