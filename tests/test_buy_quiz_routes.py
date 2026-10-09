"""Buy-mode quiz routes (/api/buy/quiz/*)."""


def test_quiz_question_returns_question_and_stage(live_seller, monkeypatch):
    client, seller, headers = live_seller
    seller.call.current_stage = "logical"
    monkeypatch.setattr("backend.routes.buy.get_quiz_question", lambda quiz_type: {"prompt": quiz_type})

    response = client.get("/api/buy/quiz/question?type=next-move", headers=headers)

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "question": {"prompt": "next-move"},
        "type": "next-move",
        "stage": "LOGICAL",
        "strategy": "CONSULTATIVE",
    }


def test_quiz_stage_rejects_missing_answer(live_seller):
    client, _seller, headers = live_seller

    response = client.post("/api/buy/quiz/stage", json={"answer": " "}, headers=headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "Answer required"


def test_quiz_stage_scores_the_answer_against_the_live_stage(live_seller):
    client, _seller, headers = live_seller

    payload = client.post(
        "/api/buy/quiz/stage", json={"answer": "intent, consultative"}, headers=headers
    ).get_json()

    assert payload["correct"] is True and payload["stage"] == "INTENT"


def test_quiz_next_move_returns_score(live_seller, monkeypatch):
    client, seller, headers = live_seller
    captured = {}

    def fake_score(response):
        captured["response"] = response
        return {"score": 9}

    monkeypatch.setattr(seller, "score_next_move", fake_score)

    response = client.post("/api/buy/quiz/next-move", json={"response": "Ask about impact"}, headers=headers)

    assert response.status_code == 200
    assert response.get_json()["score"] == 9
    assert captured == {"response": "Ask about impact"}
