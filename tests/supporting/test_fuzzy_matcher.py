"""Unit tests for fuzzy_matcher.py - Intent recognition and fuzzy matching."""

import pytest
from kalap_v2.fuzzy_matcher import FuzzyMatcher


@pytest.mark.unit
@pytest.mark.fuzzy
@pytest.mark.fast
class TestFuzzyMatcherIntents:
    """Test intent matching functionality."""
    
    def test_exact_keyword_match(self, fuzzy_matcher, sample_intents):
        """Test exact keyword matching returns correct intent."""
        result = fuzzy_matcher.match_intent("What's the budget?", sample_intents)
        assert result == "budget_inquiry"
    
    def test_typo_tolerance(self, fuzzy_matcher, sample_intents):
        """Test fuzzy matching handles typos (rapidfuzz feature)."""
        result = fuzzy_matcher.match_intent("Whats the budjet?", sample_intents)
        assert result == "budget_inquiry"
    
    def test_partial_match(self, fuzzy_matcher, sample_intents):
        """Test partial_ratio algorithm handles substring matches."""
        result = fuzzy_matcher.match_intent("I have a major problem with sales", sample_intents)
        assert result == "pain_point"
    
    def test_no_match_returns_none(self, fuzzy_matcher, sample_intents):
        """Test unmatched input returns None."""
        result = fuzzy_matcher.match_intent("random unrelated text", sample_intents)
        assert result is None
    
    def test_multiple_keywords_boost_score(self, fuzzy_matcher):
        """Test multiple keyword matches increase confidence."""
        intents = {"strong_match": ["budget", "cost", "price"]}
        result = fuzzy_matcher.match_intent("What's the budget and cost?", intents)
        assert result == "strong_match"


@pytest.mark.unit
@pytest.mark.fuzzy
@pytest.mark.fast
class TestFuzzyMatcherObjections:
    """Test objection signal detection."""
    
    def test_detect_price_objection(self, fuzzy_matcher):
        """Test price objection detection."""
        signals = fuzzy_matcher.detect_objection_signals("That's too expensive")
        assert len(signals) > 0
        assert any(s['type'] == 'price_sensitivity' for s in signals)
    
    def test_detect_time_objection(self, fuzzy_matcher):
        """Test time-related objection detection."""
        signals = fuzzy_matcher.detect_objection_signals("I don't have time for this right now")
        assert len(signals) > 0
        assert any(s['type'] == 'time_objection' for s in signals)
    
    def test_confidence_scoring(self, fuzzy_matcher):
        """Test objection signals include confidence scores."""
        signals = fuzzy_matcher.detect_objection_signals("Too expensive and no budget")
        assert all('confidence' in s for s in signals)
        assert all(0 <= s['confidence'] <= 1 for s in signals)
    
    def test_no_objections_empty_list(self, fuzzy_matcher):
        """Test clean input returns empty list."""
        signals = fuzzy_matcher.detect_objection_signals("This sounds great!")
        assert signals == []


@pytest.mark.unit
@pytest.mark.fuzzy
@pytest.mark.fast
class TestFuzzyMatcherModes:
    """Test mode configuration."""
    
    def test_simple_mode_default(self, fuzzy_matcher):
        """Test simple mode is default."""
        assert fuzzy_matcher.mode == "simple"
    
    def test_advanced_mode_stores_mode(self):
        """Test advanced mode can be set (reserved for future use)."""
        matcher = FuzzyMatcher(mode="advanced")
        assert matcher.mode == "advanced"
        # Advanced mode uses same logic as simple for now
        result = matcher.match_intent("test", {"test_intent": ["test"]})
        assert result == "test_intent"


@pytest.mark.unit
@pytest.mark.fuzzy
@pytest.mark.fast
class TestFuzzyMatcherTransitions:
    """Test phase transition readiness detection."""
    
    def test_detect_transition_readiness(self, fuzzy_matcher):
        """Test transition signal detection between phases."""
        is_ready, confidence = fuzzy_matcher.detect_transition_readiness(
            "So based on what you've told me...",
            "intent",
            "logical_certainty"
        )
        assert isinstance(is_ready, bool)
        assert 0 <= confidence <= 1
    
    def test_invalid_transition_returns_false(self, fuzzy_matcher):
        """Test invalid phase transition returns False."""
        is_ready, confidence = fuzzy_matcher.detect_transition_readiness(
            "random text",
            "invalid_phase",
            "also_invalid"
        )
        assert is_ready is False
        assert confidence == 0.0
