"""Unit tests for question_router.py - Question selection and routing."""

import pytest
from jinja2 import Template


@pytest.mark.unit
@pytest.mark.router
@pytest.mark.fast
class TestQuestionRouterSelection:
    """Test question selection logic."""
    
    def test_get_opening_question_intent_phase(self, question_router):
        """Test opening question for intent phase."""
        question = question_router.get_opening_question('intent')
        assert isinstance(question, str)
        assert len(question) > 0
    
    def test_get_probe_question(self, question_router):
        """Test probe question generation."""
        probe = question_router.get_probe_question('intent', probe_type='emotion')
        assert isinstance(probe, str)
    
    def test_probe_type_specificity(self, question_router):
        """Test different probe types return appropriate questions."""
        emotion_probe = question_router.get_probe_question('intent', 'emotion')
        specificity_probe = question_router.get_probe_question('intent', 'specificity')
        # Questions should differ based on probe type
        assert emotion_probe != specificity_probe


@pytest.mark.unit
@pytest.mark.router
@pytest.mark.fast
class TestQuestionRouterContext:
    """Test context-aware question formatting."""
    
    def test_format_question_with_context(self, question_router, context_tracker, sample_session_id):
        """Test template rendering with context variables."""
        context_tracker.set_capture(sample_session_id, 'tangible_outcome', 'increase sales', 0.8)
        question = "How will you achieve {tangible_outcome}?"
        formatted = question_router.format_question_with_context(question, sample_session_id)
        assert "increase sales" in formatted
        assert "{tangible_outcome}" not in formatted
    
    def test_format_question_no_variables(self, question_router, sample_session_id):
        """Test formatting works without template variables."""
        question = "Tell me more about that."
        formatted = question_router.format_question_with_context(question, sample_session_id)
        assert formatted == question
    
    def test_multiple_variables_formatting(self, question_router, context_tracker, sample_session_id):
        """Test multiple variable substitution."""
        context_tracker.set_capture(sample_session_id, 'problem', 'low conversion', 0.7)
        context_tracker.set_capture(sample_session_id, 'goal', '30% increase', 0.9)
        question = "So you want {goal} despite {problem}?"
        formatted = question_router.format_question_with_context(question, sample_session_id)
        assert "30% increase" in formatted
        assert "low conversion" in formatted


@pytest.mark.unit
@pytest.mark.router
@pytest.mark.fast
class TestQuestionRouterPhaseLogic:
    """Test phase-based routing logic."""
    
    def test_should_probe_deeper_insufficient_answer(self, question_router, sample_session_id):
        """Test probe recommendation for insufficient answers."""
        should_probe = question_router.should_probe_deeper(
            sample_session_id,
            "maybe",
            "tangible_outcome"
        )
        assert should_probe is True
    
    def test_should_probe_deeper_sufficient_answer(self, question_router, sample_session_id):
        """Test no probe for sufficient answers."""
        should_probe = question_router.should_probe_deeper(
            sample_session_id,
            "I want to increase my sales revenue by 50% within the next quarter by improving my closing techniques",
            "tangible_outcome"
        )
        assert should_probe is False


@pytest.mark.unit
@pytest.mark.router
@pytest.mark.fast
class TestQuestionRouterNextQuestion:
    """Test get_next_question orchestration."""
    
    def test_get_next_question_returns_string(self, question_router, sample_session_id):
        """Test get_next_question always returns a question."""
        question = question_router.get_next_question(sample_session_id)
        assert isinstance(question, str)
        assert len(question) > 0
    
    def test_get_next_question_with_user_input(self, question_router, sample_session_id):
        """Test question selection considers user input."""
        question = question_router.get_next_question(
            sample_session_id,
            user_input="I need help with sales"
        )
        assert isinstance(question, str)
