# Focused unit tests for prospect-mode session evaluation.


import core.prospect_evaluator as evaluator
from core.prospect_session import ProspectState


def _config(scoring_enabled=True, feedback_style="coaching"):
    return {
        "prospect_mode": {
            "scoring_enabled": scoring_enabled,
            "feedback_style": feedback_style,
            "max_turns": 8,
        },
        "evaluation": {
            "criteria": {
                "needs_discovery": {"weight": 0.6, "description": "Discovery"},
                "rapport_building": {"weight": 0.4, "description": "Rapport"},
            }
        },
    }


def test_deterministic_scores_default_to_neutral_when_no_sales_history():
    criteria = _config()["evaluation"]["criteria"]

    scores = evaluator._build_deterministic_criteria_scores([], criteria)

    assert scores == {
        "needs_discovery": {"score": 40, "feedback": "Not enough evidence to score this criterion yet."},
        "rapport_building": {"score": 40, "feedback": "Not enough evidence to score this criterion yet."},
    }


def test_evaluate_prospect_session_uses_deterministic_fallback_when_scoring_disabled(monkeypatch):
    monkeypatch.setattr(evaluator, "load_prospect_config", lambda: _config(scoring_enabled=False))
    state = ProspectState(readiness=0.2, difficulty="easy", product_type="default")

    result = evaluator.evaluate_prospect_session([], state)

    assert result["overall_score"] == 40
    assert result["grade"] == "F"
    assert result["criteria_scores"] == {
        "needs_discovery": {"score": 40, "feedback": "Not enough evidence to score this criterion yet."},
        "rapport_building": {"score": 40, "feedback": "Not enough evidence to score this criterion yet."},
    }
    assert result["summary"] == "Foundational attempt; focus on core questioning and structure. Outcome: active."
    assert result["coach_tip"] == "Ask one open question that surfaces root cause, not symptoms."
