"""TDD Tests for Quiz Assessment Feature

Test-first approach for deterministic quiz evaluation.
Run: pytest tests/test_quiz.py -v
"""
from helpers import MockBot


# =============================================================================
# Stage Quiz Tests (Deterministic - TDD)
# =============================================================================

class TestStageQuizEvaluation:
    """TDD tests for stage identification quiz."""

    def test_exact_match_correct(self):
        """User provides exact stage and strategy - should be correct."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="logical", strategy="consultative")

        result = evaluate_stage_quiz("logical consultative", bot)

        assert result["correct"] is True
        assert result["score"] == 1

    def test_case_insensitive(self):
        """Stage matching should be case-insensitive."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="logical", strategy="consultative")

        result = evaluate_stage_quiz("LOGICAL CONSULTATIVE", bot)

        assert result["correct"] is True

    def test_natural_language_accepted(self):
        """User can provide natural language answer containing keywords."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="emotional", strategy="consultative")

        result = evaluate_stage_quiz(
            "We're in the emotional stage using a consultative approach",
            bot
        )

        assert result["correct"] is True

    def test_stage_only_is_partial(self):
        """Providing only stage (no strategy) should be partial/incorrect."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="pitch", strategy="transactional")

        result = evaluate_stage_quiz("pitch", bot)

        # Must include both stage AND strategy to be correct
        assert result["correct"] is False
        assert result["score"] == 0

    def test_wrong_stage_incorrect(self):
        """Wrong stage should be incorrect even with right strategy."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="logical", strategy="consultative")

        result = evaluate_stage_quiz("pitch consultative", bot)

        assert result["correct"] is False

    def test_wrong_strategy_incorrect(self):
        """Wrong strategy should be incorrect even with right stage."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="pitch", strategy="consultative")

        result = evaluate_stage_quiz("pitch transactional", bot)

        assert result["correct"] is False

    def test_expected_values_returned(self):
        """Expected stage and strategy should always be returned."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="objection", strategy="transactional")

        result = evaluate_stage_quiz("wrong answer", bot)

        assert result["expected"]["stage"] == "objection"
        assert result["expected"]["strategy"] == "transactional"

    def test_feedback_on_correct(self):
        """Correct answer should have positive feedback with stage info."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="intent", strategy="consultative")

        result = evaluate_stage_quiz("intent consultative", bot)

        assert "Correct" in result["feedback"]
        assert "INTENT" in result["feedback"] or "intent" in result["feedback"].lower()

    def test_feedback_on_incorrect(self):
        """Incorrect answer should reveal correct answer in feedback."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="logical", strategy="consultative")

        result = evaluate_stage_quiz("pitch transactional", bot)

        assert "logical" in result["feedback"].lower()
        assert "consultative" in result["feedback"].lower()

    def test_user_answer_preserved(self):
        """Original user answer should be included in result."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot()

        result = evaluate_stage_quiz("my custom answer", bot)

        assert result["user_answer"] == "my custom answer"


class TestStageQuizAllStates:
    """Test stage quiz across all FSM state combinations."""

    def test_consultative_all_stages(self):
        """Quiz works for all consultative stages."""
        from chatbot.quiz import evaluate_stage_quiz

        stages = ["intent", "logical", "emotional", "pitch", "objection"]
        for stage in stages:
            bot = MockBot(stage=stage, strategy="consultative")
            result = evaluate_stage_quiz(f"{stage} consultative", bot)
            assert result["correct"] is True, f"Failed for {stage}"

    def test_transactional_all_stages(self):
        """Quiz works for all transactional stages."""
        from chatbot.quiz import evaluate_stage_quiz

        stages = ["intent", "pitch", "objection"]
        for stage in stages:
            bot = MockBot(stage=stage, strategy="transactional")
            result = evaluate_stage_quiz(f"{stage} transactional", bot)
            assert result["correct"] is True, f"Failed for {stage}"

    def test_intent_discovery_mode(self):
        """Quiz works for intent discovery mode (before strategy set)."""
        from chatbot.quiz import evaluate_stage_quiz
        bot = MockBot(stage="intent", strategy="intent")

        result = evaluate_stage_quiz("intent intent", bot)

        assert result["correct"] is True


# =============================================================================
# Quiz Question Generation Tests
# =============================================================================

class TestQuizQuestionGeneration:
    """Test quiz question retrieval from config."""

    def test_get_stage_question(self):
        """Should return a stage quiz question."""
        from chatbot.quiz import get_quiz_question

        question = get_quiz_question("stage")

        assert isinstance(question, str)
        assert len(question) > 10
        assert "?" in question

    def test_get_next_move_question(self):
        """Should return a next-move quiz question."""
        from chatbot.quiz import get_quiz_question

        question = get_quiz_question("next_move")

        assert isinstance(question, str)
        assert len(question) > 10

    def test_get_direction_question(self):
        """Should return a direction quiz question."""
        from chatbot.quiz import get_quiz_question

        question = get_quiz_question("direction")

        assert isinstance(question, str)
        assert len(question) > 10

    def test_invalid_type_returns_fallback(self):
        """Invalid quiz type should return a sensible fallback."""
        from chatbot.quiz import get_quiz_question

        question = get_quiz_question("invalid_type")

        assert isinstance(question, str)
        assert len(question) > 0


# =============================================================================
# Stage Rubric Loading Tests
# =============================================================================

class TestStageRubricLoading:
    """Test loading stage rubrics from config."""

    def test_load_consultative_logical_rubric(self):
        """Should load rubric for consultative/logical stage."""
        from chatbot.quiz import get_stage_rubric

        rubric = get_stage_rubric("logical", "consultative")

        assert "goal" in rubric
        assert "advance_when" in rubric
        assert "key_concepts" in rubric
        assert isinstance(rubric["key_concepts"], list)

    def test_load_transactional_pitch_rubric(self):
        """Should load rubric for transactional/pitch stage."""
        from chatbot.quiz import get_stage_rubric

        rubric = get_stage_rubric("pitch", "transactional")

        assert "goal" in rubric
        assert len(rubric["goal"]) > 0

    def test_fallback_for_unknown_stage(self):
        """Should return fallback rubric for unknown stage."""
        from chatbot.quiz import get_stage_rubric

        rubric = get_stage_rubric("unknown_stage", "consultative")

        assert isinstance(rubric, dict)
        assert "goal" in rubric  # Should have default structure


# =============================================================================
# LLM Output Validation Tests
# =============================================================================

class TestScoreClamping:
    """Test that LLM-returned scores are clamped to valid range."""

    def test_valid_score_unchanged(self):
        """Score within 0-100 passes through."""
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score(75) == 75

    def test_negative_score_clamped_to_zero(self):
        """Negative LLM score clamped to 0."""
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score(-5) == 0

    def test_over_hundred_clamped(self):
        """Score above 100 clamped to 100."""
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score(500) == 100

    def test_non_numeric_returns_default(self):
        """Non-numeric score falls back to default."""
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score("abc") == 50
        assert _clamp_score(None) == 50


class TestEnumValidation:
    """Test that LLM-returned enum values are validated."""

    def test_valid_alignment_values(self):
        """All valid alignment values are accepted."""
        from chatbot.quiz import _ALIGNMENT_VALUES
        assert _ALIGNMENT_VALUES == {"strong", "partial", "weak"}

    def test_valid_understanding_values(self):
        """All valid understanding values are accepted."""
        from chatbot.quiz import _UNDERSTANDING_VALUES
        assert _UNDERSTANDING_VALUES == {"excellent", "good", "partial", "needs_work"}


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
