"""Sell-mode session evaluation."""

import core.sell_mode.sell_evaluator as evaluator
from core.sell_mode.buyer_state import BuyerState
from core.infra.loader import load_buyer_config

NO_EVIDENCE = load_buyer_config()["evaluation"]["feedback"]["no_evidence"]


def _config():
    """The real buyer config with only two criteria, so the weighting is easy to read."""
    config = load_buyer_config()
    criteria = config["evaluation"]["criteria"]
    config["evaluation"]["criteria"] = {
        "needs_discovery": {**criteria["needs_discovery"], "weight": 0.6},
        "rapport_building": {**criteria["rapport_building"], "weight": 0.4},
    }
    return config


def test_criteria_score_empty_when_the_salesperson_said_nothing():
    scores = evaluator._criteria_scores([], _config()["evaluation"])

    assert scores == {
        "needs_discovery": {"score": 40, "feedback": NO_EVIDENCE, "measured": False},
        "rapport_building": {"score": 40, "feedback": NO_EVIDENCE, "measured": False},
    }


def test_empty_session_scores_neutral(monkeypatch):
    monkeypatch.setattr(evaluator, "load_buyer_config", _config)
    state = BuyerState(readiness=0.2, difficulty="easy", product_type="default")

    result = evaluator.evaluate_sell_session([], state)

    assert result["overall_score"] == 40
    assert result["grade"] == "F"
    assert result["criteria_scores"] == {
        "needs_discovery": {"score": 40, "feedback": NO_EVIDENCE, "measured": False},
        "rapport_building": {"score": 40, "feedback": NO_EVIDENCE, "measured": False},
    }
    assert result["summary"] == "Foundational attempt; focus on core questioning and structure. Outcome: no decision yet."
    assert result["coach_tip"] == "Ask one open question that surfaces root cause, not symptoms."


def _objection_texts():
    hints = load_buyer_config()["evaluation"]["hints"]
    return hints["objection_cues"][0], hints["objection_response"][0]


def test_objections_all_answered_get_praise_not_advice():
    """Found live: 100% on objection handling, under the advice to 'acknowledge concerns directly'."""
    cue, response = _objection_texts()
    history = [{"role": "user", "content": "What made you take the call?"},
               {"role": "assistant", "content": f"Well, {cue}, to be honest."},
               {"role": "user", "content": f"I {response} completely. What would make it worth it?"}]
    oh = evaluator._criteria_scores(history, load_buyer_config()["evaluation"])["objection_handling"]
    criteria = load_buyer_config()["evaluation"]["criteria"]["objection_handling"]
    assert oh["score"] == 100 and oh["feedback"] == criteria["praise"]


def test_no_objection_says_so():
    history = [{"role": "user", "content": "What made you take the call?"}, {"role": "assistant", "content": "Curious."}]
    oh = evaluator._criteria_scores(history, load_buyer_config()["evaluation"])["objection_handling"]
    assert oh["feedback"] == load_buyer_config()["evaluation"]["criteria"]["objection_handling"]["none"]
    assert oh["measured"] is False
