"""Quiz scoring and question selection."""

import json

import pytest

import core.quiz as quiz
from core.providers.base import LLMResponse
from core.services.provider_router import ProviderChatResult

_CONFIG = quiz.load_quiz()


def _with_stages(monkeypatch, **stages):
    """The real quiz config with only the given consultative stages."""
    monkeypatch.setattr(quiz, "load_quiz", lambda: {**_CONFIG, "stages": {"consultative": stages}})


class _RaisingProvider:
    def chat_with_fallback(self, *_args, **_kwargs):
        raise RuntimeError("provider unavailable")


class _JsonProvider:
    def __init__(self, content: str):
        self._content = content

    def chat_with_fallback(self, *_args, **_kwargs):
        return ProviderChatResult(LLMResponse(content=self._content), "stub", "stub-model")


def test_get_stage_rubric_reads_the_configured_rubric_and_fails_loud_on_a_missing_one(monkeypatch):
    rubric = {"goal": "Confirm the goal", "advance_when": "Goal is clear", "key_concepts": ["Ask open questions"]}
    _with_stages(monkeypatch, intent=rubric)

    assert quiz.get_stage_rubric("intent", "consultative") == rubric
    with pytest.raises(KeyError):
        quiz.get_stage_rubric("missing", "consultative")


def test_every_stage_has_a_rubric_and_a_plain_name():
    from core.enums import Stage

    for stage in Stage:
        assert quiz.get_stage_rubric(stage, "consultative")["key_concepts"]
        assert stage.value in _CONFIG["stage_names"]


def test_get_quiz_question_prefers_configured_list_and_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(
        quiz,
        "load_quiz",
        lambda: {
            "questions": {
                "stage": ["Stage question 1", "Stage question 2"],
                "next_move": ["Next move question"],
                "default": ["How would you proceed?"],
            }
        },
    )
    monkeypatch.setattr(quiz.random, "choice", lambda items: items[-1])

    assert quiz.get_quiz_question("stage") == "Stage question 2"
    assert quiz.get_quiz_question("next-move") == "Next move question"
    assert quiz.get_quiz_question("unknown-type") == "How would you proceed?"


@pytest.mark.parametrize(
    "answer,expected",
    [
        (
            "We are in the logical stage and the consultative strategy.",
            (True, 1, "Right - Understanding the problem, Consultative approach."),
        ),
        (
            "It is not logical, but it is consultative.",
            (False, 0.5, "The approach is right (Consultative), but you're in Understanding the problem now."),
        ),
        (
            "It is logical, but not consultative.",
            (False, 0.5, "The stage is right (Understanding the problem), but this is the Consultative approach."),
        ),
        (
            "This is not logical and not consultative.",
            (False, 0, "Not this time - it's Understanding the problem (Consultative approach)."),
        ),
    ],
)
def test_stage_answer_scores_partial_credit_and_respects_negation(answer, expected):
    result = quiz.score_stage_answer(answer, "logical", "consultative")

    assert result["correct"] is expected[0]
    assert result["score"] == expected[1]
    assert result["feedback"] == expected[2]
    assert result["expected"] == {"stage": "Understanding the problem", "strategy": "Consultative"}


def test_next_move_merges_llm_feedback_and_uses_score_fallback(monkeypatch):
    _with_stages(monkeypatch, logical={
        "goal": "Surface the problem",
        "advance_when": "The problem is clear",
        "key_concepts": ["Ask about budget", "Use an open question"],
    })

    llm_payload = {
        "score": 110,
        "alignment": "unexpected",
        "feedback": "Great focus.",
        "strengths": ["Used an open question."],
        "improvements": ["Add more detail."],
    }
    provider = _JsonProvider(content=json.dumps(llm_payload))

    result = quiz.score_next_move(
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


def test_direction_falls_back_to_rule_scoring_when_llm_fails(monkeypatch):
    _with_stages(monkeypatch, logical={
        "goal": "Surface the problem",
        "advance_when": "The problem is clear",
        "key_concepts": ["Why the problem matters", "Next steps"],
    })

    result = quiz.score_direction(
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

    result = quiz.score_stage_answer("no idea", Stage.INTENT, "consultative")

    assert "STAGE." not in result["feedback"].upper() and "FSM" not in result["feedback"].upper()
    assert result["expected"]["stage"] == "Finding out what they want"
    assert "Close" not in result["feedback"]


def test_the_plain_stage_name_is_accepted_as_an_answer():
    result = quiz.score_stage_answer("Understanding the problem, consultative", "logical", "consultative")

    assert result["correct"] is True


def test_no_quiz_question_mentions_fsm():
    config = quiz.load_quiz()
    assert not any("FSM" in q for qs in config["questions"].values() for q in qs)


def test_sell_quiz_asks_about_the_sellers_weakest_turn_and_scores_a_better_line():
    turns = [
        {"turn": 1, "seller": "Great weather.", "rating": 2, "buyer_before": "My van keeps breaking down."},
        {"turn": 2, "seller": "What breaks?", "rating": 4, "buyer_before": "Hmm."},
    ]

    asked = quiz.build_sell_question(turns)
    assert asked["turn"] == 1 and "Great weather." in asked["question"]
    assert quiz.build_sell_question([]) is None

    better = quiz.score_sell_answer("What happens when your van keeps breaking down?", turns[0])
    worse = quiz.score_sell_answer("ok", turns[0])
    assert better["score"] > worse["score"]
    assert better["feedback"].startswith("Better")


def test_sell_quiz_explains_why_in_the_turn_reviews_own_words():
    from core.turn_rating import REASONS

    turn = {"turn": 1, "seller": "Great weather.", "rating": 2,
            "buyer_before": "My van keeps breaking down.", "signals": ["closed_question"]}

    result = quiz.score_sell_answer("What happens when your van keeps breaking down?", turn)

    assert REASONS["open_question"] in result["strengths"]
    assert result["before"] == [{"text": REASONS["closed_question"], "good": False}]
    # No signals recorded (older session): nothing invented.
    assert quiz.score_sell_answer("ok", {**turn, "signals": []})["before"] == []
