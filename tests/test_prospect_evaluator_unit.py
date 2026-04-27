# Focused unit tests for prospect-mode session evaluation.

import json

import core.prospect_evaluator as evaluator
from core.prospect_session import ProspectState
from core.providers.base import LLMResponse


class _StaticProvider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    def chat(self, messages, temperature=0.3, max_tokens=800):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return LLMResponse(content=json.dumps(self.payload))


class _RaisingProvider:
    def chat(self, *_args, **_kwargs):
        raise RuntimeError("provider unavailable")


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


def test_build_evaluation_blends_llm_and_deterministic_results():
    criteria = _config()["evaluation"]["criteria"]
    deterministic = {
        "criteria_scores": {
            "needs_discovery": {"score": 80, "feedback": "Deterministic discovery note."},
            "rapport_building": {"score": 60, "feedback": "Deterministic rapport note."},
        },
        "strengths": ["Deterministic strength."],
        "improvements": ["Deterministic improvement."],
        "summary": "Deterministic summary.",
        "coach_tip": "Deterministic tip.",
    }
    raw_result = {
        "criteria_scores": {
            "needs_discovery": {"score": 100, "feedback": "LLM discovery note."},
            "rapport_building": {"score": 50, "feedback": "LLM rapport note."},
        },
        "strengths": ["LLM strength."],
        "improvements": ["LLM improvement."],
        "summary": "",
    }

    result = evaluator._build_evaluation(raw_result, criteria, "active", deterministic)

    assert result["criteria_scores"] == {
        "needs_discovery": {"score": 94, "feedback": "LLM discovery note."},
        "rapport_building": {"score": 53, "feedback": "LLM rapport note."},
    }
    assert result["overall_score"] == 78
    assert result["grade"] == "C"
    assert result["strengths"] == ["LLM strength.", "Deterministic strength."]
    assert result["improvements"] == ["LLM improvement.", "Deterministic improvement."]
    assert result["summary"] == "Deterministic summary."
    assert result["coach_tip"] == "Deterministic tip."
    assert result["outcome"] == "active"


def test_evaluate_prospect_session_blends_llm_with_deterministic_pack(monkeypatch):
    monkeypatch.setattr(evaluator, "load_prospect_config", lambda: _config(scoring_enabled=True))
    provider = _StaticProvider(
        {
            "criteria_scores": {
                "needs_discovery": {"score": 100, "feedback": "LLM discovery note."},
                "rapport_building": {"score": 100, "feedback": "LLM rapport note."},
            },
            "strengths": ["LLM strength."],
            "improvements": ["LLM improvement."],
            "summary": "",
        }
    )
    state = ProspectState(readiness=0.2, difficulty="easy", product_type="default")

    result = evaluator.evaluate_prospect_session(provider, [], state, "Default context")

    assert provider.calls and provider.calls[0]["temperature"] == 0.3
    assert result["criteria_scores"] == {
        "needs_discovery": {"score": 82, "feedback": "LLM discovery note."},
        "rapport_building": {"score": 82, "feedback": "LLM rapport note."},
    }
    assert result["overall_score"] == 82
    assert result["grade"] == "B"
    assert result["strengths"] == ["LLM strength.", "Consistent baseline across criteria."]
    assert result["improvements"] == [
        "LLM improvement.",
        "Ask one open question that surfaces root cause, not symptoms.",
        "Start with a brief validation before probing deeper.",
    ]
    assert result["summary"] == "Foundational attempt; focus on core questioning and structure. Outcome: active."
    assert result["coach_tip"] == "Ask one open question that surfaces root cause, not symptoms."


def test_evaluate_prospect_session_uses_deterministic_fallback_when_scoring_disabled(monkeypatch):
    monkeypatch.setattr(evaluator, "load_prospect_config", lambda: _config(scoring_enabled=False))
    state = ProspectState(readiness=0.2, difficulty="easy", product_type="default")

    result = evaluator.evaluate_prospect_session(_RaisingProvider(), [], state, "Default context")

    assert result["overall_score"] == 40
    assert result["grade"] == "F"
    assert result["criteria_scores"] == {
        "needs_discovery": {"score": 40, "feedback": "Not enough evidence to score this criterion yet."},
        "rapport_building": {"score": 40, "feedback": "Not enough evidence to score this criterion yet."},
    }
    assert result["summary"] == "Foundational attempt; focus on core questioning and structure. Outcome: active."
    assert result["coach_tip"] == "Ask one open question that surfaces root cause, not symptoms."
