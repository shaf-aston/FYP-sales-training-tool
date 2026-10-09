"""Each mode answers on its own path: /api/buy and /api/sell."""

BUY_PRODUCT = "high_ticket_sales_mentorship"  # a scripted product in script/engine.yaml


def test_buy_mode_answers(sell_client):
    started = sell_client.post("/api/buy/init", json={"product_type": BUY_PRODUCT})
    assert started.status_code == 200, started.get_json()
    headers = {"X-Session-ID": started.get_json()["session_id"]}

    replied = sell_client.post("/api/buy/chat", json={"message": "I want more freedom"}, headers=headers)
    assert replied.status_code == 200, replied.get_json()
    assert replied.get_json()["message"]

    asked = sell_client.get("/api/buy/quiz/question?type=stage", headers=headers)
    assert asked.status_code == 200, asked.get_json()
    assert asked.get_json()["type"] == "stage"


def test_sell_mode_answers(sell_client):
    groups = sell_client.get("/api/sell/product-groups")
    assert groups.status_code == 200
    assert set(groups.get_json()["groups"]) == {"transactional", "consultative"}

    started = sell_client.post("/api/sell/init", json={"difficulty": "medium", "product_type": "default"})
    assert started.status_code == 200, started.get_json()
    headers = {"X-Session-ID": started.get_json()["session_id"]}

    replied = sell_client.post("/api/sell/chat", json={"message": "What matters most to you?"}, headers=headers)
    assert replied.status_code == 200, replied.get_json()
    assert replied.get_json()["message"]
