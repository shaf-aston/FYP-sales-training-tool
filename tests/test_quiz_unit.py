"""Focused unit tests for quiz scoring and question selection."""

import json

import pytest

import core.quiz as quiz
from core.providers.base import LLMResponse
from core.services.provider_router import ProviderChatResult


class _RaisingProvider:
    def chat_with_fallback(self, *_args, **_kwargs):
        raise RuntimeError("provider unavailable")


class _JsonProvider:
    def __init__(self, content: str):
        self._content = content

    def chat_with_fallback(self, *_args, **_kwargs):
        return ProviderChatResult(LLMResponse(content=self._content), "stub", "stub-model")


def test_get_stage_rubric_uses_configured_values_and_falls_back(monkeypatch):
    monkeypatch.setattr(
        quiz,
        "_quiz_config",
        {
            "stages": {
                "consultative": {
                    "intent": {
                        "goal": "Confirm the goal",
                        "advance_when": "Goal is clear",
                        "key_concepts": ["Ask open questions"],
                        "next_stage": "logical",
                    }
                }
            }
        },
        raising=False,
    )

    assert quiz.get_stage_rubric("intent", "intent") == {
        "goal": "Confirm the goal",
        "advance_when": "Goal is clear",
        "key_concepts": ["Ask open questions"],
        "next_stage": "logical",
    }
    assert quiz.get_stage_rubric("missing", "intent") == {
        "goal": "Complete the missing stage",
        "advance_when": "Stage objectives are met",
        "key_concepts": ["Listen actively", "Ask relevant questions"],
        "next_stage": None,
    }


def test_get_quiz_question_prefers_configured_list_and_fallbacks(monkeypatch):
    monkeypatch.setattr(
        quiz,
        "_quiz_config",
        {
            "questions": {
                "stage": ["Stage question 1", "Stage question 2"],
                "next_move": ["Next move question"],
            }
        },
        raising=False,
    )
    monkeypatch.setattr(quiz.random, "choice", lambda items: items[-1])

    assert quiz.get_quiz_question("stage") == "Stage question 2"
    assert quiz.get_quiz_question("next-move") == "Next move question"
    assert quiz.get_quiz_question("unknown-type") == "How would you proceed?"


@pytest.mark.parametrize(
    "answer,current_stage,flow_type,expected",
    [
        (
            "We are in the logical stage and the consultative strategy.",
            "logical",
            "consultative",
            (True, 1, "Right - Understanding the problem, Consultative approach."),
        ),
        (
            "It is not logical, but it is transactional.",
            "logical",
            "transactional",
            (False, 0.5, "The approach is right (Quick sale), but you're in Understanding the problem now."),
        ),
        (
            "This is not logical and not transactional.",
            "logical",
            "transactional",
            (False, 0, "Not this time - it's Understanding the problem (Quick sale approach)."),
        ),
    ],
)
def test_stage_answer_scores_partial_credit_and_respects_negation(
    answer, current_stage, flow_type, expected
):
    result = quiz.test_quiz_stage_answer(answer, current_stage, flow_type)

    assert result["correct"] is expected[0]
    assert result["score"] == expected[1]
    assert result["feedback"] == expected[2]
    assert result["expected"] == {
        "stage": "Understanding the problem",
        "strategy": "Quick sale" if flow_type == "transactional" else "Consultative",
    }


def test_next_move_merges_llm_feedback_and_uses_score_fallback(monkeypatch):
    monkeypatch.setattr(
        quiz,
        "_quiz_config",
        {
            "stages": {
                "consultative": {
                    "logical": {
                        "goal": "Surface the problem",
                        "advance_when": "The problem is clear",
                        "key_concepts": ["Ask about budget", "Use an open question"],
                        "next_stage": "emotional",
                    }
                }
            }
        },
        raising=False,
    )

    llm_payload = {
        "score": 110,
        "alignment": "unexpected",
        "feedback": "Great focus.",
        "strengths": ["Used an open question."],
        "improvements": ["Add more detail."],
    }
    provider = _JsonProvider(content=json.dumps(llm_payload))

    result = quiz.test_quiz_next_move(
        "How is your budget allocated today?",
        provider,
        "logical",
        "consultative",
        last_user_message="We need a faster solution.",
    )

    assert result["score"] == 46  # rules only: the LLM's 110 never moves the score
    assert result["alignment"] == "partial"
    assert result["feedback"] == "Partly aligned, but tighten stage focus. Great focus."
    assert result["strengths"] == [
        "Response referenced key stage concepts.",
        "Used an open question to keep discovery moving.",
        "Used an open question.",
    ]
    assert result["improvements"] == [
        "Reference one concrete detail from the customer's last message.",
        "Add more detail.",
    ]
    assert result["coach_tip"] == "Focus next on this concept: Use an open question."


def test_direction_falls_back_to_deterministic_scoring_when_llm_fails(monkeypatch):
    monkeypatch.setattr(
        quiz,
        "_quiz_config",
        {
            "stages": {
                "consultative": {
                    "logical": {
                        "goal": "Surface the problem",
                        "advance_when": "The problem is clear",
                        "key_concepts": ["Why the problem matters", "Next steps"],
                        "next_stage": "emotional",
                    }
                }
            }
        },
        raising=False,
    )

    result = quiz.test_quiz_direction(
        "First I will ask why the problem matters, then I will outline the next steps because it fits the goal.",
        _RaisingProvider(),
        "logical",
        "consultative",
    )

    assert result["score"] == 90
    assert result["understanding"] == "excellent"
    assert result["feedback"] == "Strong strategic direction for this stage."
    assert result["key_concepts_got"] == ["Why the problem matters", "Next steps"]
    assert result["key_concepts_missed"] == []


def test_stage_feedback_never_shows_raw_enums_or_jargon():
    from core.enums import Stage

    result = quiz.test_quiz_stage_answer("no idea", Stage.INTENT, "intent")

    assert "STAGE." not in result["feedback"].upper() and "FSM" not in result["feedback"].upper()
    assert result["expected"]["stage"] == "Finding out what they want"
    assert "Close" not in result["feedback"]


def test_the_plain_stage_name_is_accepted_as_an_answer():
    result = quiz.test_quiz_stage_answer(
        "Understanding the problem, consultative", "logical", "consultative"
    )

    assert result["correct"] is True


def test_no_quiz_question_mentions_fsm():
    config = quiz._load_quiz_config()
    assert not any("FSM" in q for qs in config["questions"].values() for q in qs)


def test_prospect_quiz_asks_about_the_sellers_weakest_turn_and_scores_a_better_line():
    turns = [
        {"turn": 1, "seller": "Great weather.", "rating": 2, "buyer_before": "My van keeps breaking down."},
        {"turn": 2, "seller": "What breaks?", "rating": 4, "buyer_before": "Hmm."},
    ]

    asked = quiz.build_prospect_question(turns)
    assert asked["turn"] == 1 and "Great weather." in asked["question"]
    assert quiz.build_prospect_question([]) is None

    better = quiz.score_prospect_answer("What happens when your van keeps breaking down?", turns[0])
    worse = quiz.score_prospect_answer("ok", turns[0])
    assert better["score"] > worse["score"]
    assert better["feedback"].startswith("Better")


def test_prospect_quiz_explains_why_in_the_turn_reviews_own_words():
    from core.selling_quality import REASONS

    turn = {"turn": 1, "seller": "Great weather.", "rating": 2,
            "buyer_before": "My van keeps breaking down.", "signals": ["closed_question"]}

    result = quiz.score_prospect_answer("What happens when your van keeps breaking down?", turn)

    assert REASONS["open_question"] in result["strengths"]
    assert result["before"] == [{"text": REASONS["closed_question"], "good": False}]
    # No signals recorded (older session): nothing invented.
    assert quiz.score_prospect_answer("ok", {**turn, "signals": []})["before"] == []
