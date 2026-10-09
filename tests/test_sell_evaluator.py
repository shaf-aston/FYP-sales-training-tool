"""Sell-mode session evaluation."""

import core.sell_evaluator as evaluator
from core.buyer_state import BuyerState
from core.loader import load_buyer_config

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
        "needs_discovery": {"score": 40, "feedback": NO_EVIDENCE},
        "rapport_building": {"score": 40, "feedback": NO_EVIDENCE},
    }


def test_empty_session_scores_neutral(monkeypatch):
    monkeypatch.setattr(evaluator, "load_buyer_config", _config)
    state = BuyerState(readiness=0.2, difficulty="easy", product_type="default")

    result = evaluator.evaluate_sell_session([], state)

    assert result["overall_score"] == 40
    assert result["grade"] == "F"
    assert result["criteria_scores"] == {
        "needs_discovery": {"score": 40, "feedback": NO_EVIDENCE},
        "rapport_building": {"score": 40, "feedback": NO_EVIDENCE},
    }
    assert result["summary"] == "Foundational attempt; focus on core questioning and structure. Outcome: active."
    assert result["coach_tip"] == "Ask one open question that surfaces root cause, not symptoms."
