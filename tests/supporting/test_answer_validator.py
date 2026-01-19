"""Unit tests for answer_validator.py - Response quality scoring."""

import pytest


@pytest.mark.unit
@pytest.mark.validator
@pytest.mark.fast
class TestAnswerValidatorBasic:
    """Test basic validation functionality."""
    
    def test_empty_input_insufficient(self, answer_validator):
        """Test empty input returns insufficient."""
        result = answer_validator.validate("", "tangible_outcome", "intent")
        assert result['sufficient'] is False
        assert result['needs_probe'] is True
    
    def test_short_input_low_score(self, answer_validator):
        """Test very short input gets low score."""
        result = answer_validator.validate("Yes", "tangible_outcome", "intent")
        assert result['score'] < 0.4
    
    def test_detailed_input_high_score(self, answer_validator, sample_user_inputs):
        """Test detailed input with keywords gets high score."""
        result = answer_validator.validate(
            sample_user_inputs['detailed'],
            "problem_articulation",
            "logical_certainty"
        )
        assert result['score'] > 0.4
        assert result['sufficient'] is True


@pytest.mark.unit
@pytest.mark.validator
@pytest.mark.fast
class TestAnswerValidatorScoring:
    """Test scoring rule components."""
    
    def test_word_count_affects_score(self, answer_validator):
        """Test longer responses score higher."""
        short = answer_validator.validate("I need help", "tangible_outcome", "intent")
        long = answer_validator.validate(
            "I need help with increasing my sales revenue by at least 30% this quarter",
            "tangible_outcome",
            "intent"
        )
        assert long['score'] > short['score']
    
    def test_emotional_content_bonus(self, answer_validator, sample_user_inputs):
        """Test emotional keywords increase score."""
        result = answer_validator.validate(
            sample_user_inputs['emotional'],
            "pain_experience",
            "intent"
        )
        assert result['score'] > 0.3
    
    def test_specificity_bonus(self, answer_validator):
        """Test numbers/details increase score."""
        result = answer_validator.validate(
            "I need to close 15 deals worth $250,000 by Q4",
            "tangible_outcome",
            "intent"
        )
        assert result['score'] > 0.5


@pytest.mark.unit
@pytest.mark.validator
@pytest.mark.fast
class TestAnswerValidatorSentiment:
    """Test sentiment analysis integration (textblob)."""
    
    def test_sentiment_detected(self, answer_validator, sample_user_inputs):
        """Test sentiment analysis provides bonus scoring."""
        result = answer_validator.validate(
            sample_user_inputs['emotional'],
            "pain_experience",
            "intent"
        )
        # Sentiment should be detected in emotional input
        assert 'sentiment_detected' in result
    
    def test_positive_sentiment_bonus(self, answer_validator):
        """Test positive sentiment affects scoring."""
        result = answer_validator.validate(
            "I'm excited about improving my sales process",
            "tangible_outcome",
            "intent"
        )
        assert result['score'] > 0.2


@pytest.mark.unit
@pytest.mark.validator
@pytest.mark.fast
class TestAnswerValidatorFeedback:
    """Test feedback generation."""
    
    def test_feedback_for_insufficient_answer(self, answer_validator):
        """Test validation provides actionable feedback."""
        result = answer_validator.validate("maybe", "tangible_outcome", "intent")
        assert len(result['feedback']) > 0
    
    def test_probe_recommendation(self, answer_validator):
        """Test get_probe_recommendation returns valid probe type."""
        validation = {
            'feedback': ['Use more emotional language.', 'Be more specific.'],
            'needs_probe': True
        }
        probe_type = answer_validator.get_probe_recommendation(validation)
        assert probe_type in ['emotion', 'specificity', 'depth']


@pytest.mark.unit
@pytest.mark.validator
@pytest.mark.fast
class TestAnswerValidatorCompletion:
    """Test completion score calculation."""
    
    def test_calculate_completion_score(self, answer_validator):
        """Test completion score between 0-1."""
        score = answer_validator.calculate_completion_score(
            "I want to increase revenue by 25% in 6 months",
            "tangible_outcome"
        )
        assert 0.0 <= score <= 1.0
    
    def test_detailed_response_high_completion(self, answer_validator, sample_user_inputs):
        """Test detailed responses get high completion scores."""
        score = answer_validator.calculate_completion_score(
            sample_user_inputs['detailed'],
            "problem_articulation"
        )
        assert score > 0.5
