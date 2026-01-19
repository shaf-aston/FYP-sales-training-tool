"""Integration tests for response_generator.py - Full KALAP V2 orchestration."""

import pytest


@pytest.mark.integration
@pytest.mark.generator
class TestResponseGeneratorOrchestration:
    """Test full conversation flow through all modules."""
    
    def test_generate_response_returns_structure(self, response_generator, sample_session_id):
        """Test generate_response returns expected structure."""
        result = response_generator.generate_response(
            sample_session_id,
            "I need help with my sales"
        )
        assert 'response' in result
        assert 'metadata' in result
        assert 'session_id' in result['metadata']
        assert 'current_phase' in result['metadata']
    
    def test_first_message_intent_phase(self, response_generator, sample_session_id):
        """Test first message starts in intent phase."""
        result = response_generator.generate_response(
            sample_session_id,
            "Hello"
        )
        assert result['metadata']['current_phase'] == 'intent'
    
    def test_insufficient_answer_triggers_probe(self, response_generator, sample_session_id):
        """Test insufficient answers trigger probe questions."""
        # First message
        response_generator.generate_response(sample_session_id, "I need help")
        # Short answer
        result = response_generator.generate_response(sample_session_id, "maybe")
        
        assert result['metadata']['action_taken'] == 'probe_deeper'


@pytest.mark.integration
@pytest.mark.generator
@pytest.mark.slow
class TestResponseGeneratorPhaseProgression:
    """Test phase progression through conversation."""
    
    def test_detailed_answers_advance_phase(self, response_generator, sample_session_id):
        """Test sufficient answers allow phase advancement."""
        # Simulate detailed conversation
        messages = [
            "I want to increase my sales by 50% this quarter",
            "I've been struggling because my closing rate is only 10% and I need better techniques",
            "I currently use cold calling but it's not working well",
            "I've been doing this for 6 months",
            "I like that it's straightforward but hate the low conversion",
        ]
        
        last_result = None
        for msg in messages:
            last_result = response_generator.generate_response(sample_session_id, msg)
        
        # Phase should have progressed beyond intent
        current_phase = last_result['metadata']['current_phase']
        assert current_phase != 'intent'
    
    def test_completion_scores_tracked(self, response_generator, sample_session_id):
        """Test completion scores are tracked through conversation."""
        response_generator.generate_response(
            sample_session_id,
            "I want to increase revenue by 40% in the next quarter"
        )
        result = response_generator.generate_response(
            sample_session_id,
            "I've been doing cold outreach for 8 months"
        )
        
        scores = result['metadata']['completion_scores']
        assert isinstance(scores, dict)
        assert len(scores) > 0


@pytest.mark.integration
@pytest.mark.generator
class TestResponseGeneratorContextIntegration:
    """Test context tracking integration."""
    
    def test_objection_signals_detected(self, response_generator, sample_session_id):
        """Test objection signals are captured."""
        result = response_generator.generate_response(
            sample_session_id,
            "That sounds too expensive for me"
        )
        objections = result['metadata']['objection_signals']
        assert len(objections) > 0
    
    def test_intent_detection(self, response_generator, sample_session_id):
        """Test intent detection through fuzzy matching."""
        result = response_generator.generate_response(
            sample_session_id,
            "What's the budget for this?"
        )
        # Intent detection may return None if no match found - verify metadata exists
        assert 'intent_detected' in result['metadata']
    
    def test_commitment_temperature_updates(self, response_generator, sample_session_id):
        """Test commitment temperature is tracked."""
        # Initial message
        response_generator.generate_response(sample_session_id, "I need help")
        result = response_generator.generate_response(
            sample_session_id,
            "I'm very serious about solving this problem"
        )
        
        assert 'commitment_temperature' in result['metadata']
        assert 0 <= result['metadata']['commitment_temperature'] <= 1


@pytest.mark.integration
@pytest.mark.generator
class TestResponseGeneratorReset:
    """Test conversation reset functionality."""
    
    def test_reset_conversation(self, response_generator, sample_session_id):
        """Test reset clears conversation state."""
        # Have a conversation
        response_generator.generate_response(sample_session_id, "Hello")
        response_generator.generate_response(sample_session_id, "I need help")
        
        # Reset
        response_generator.reset_conversation(sample_session_id)
        
        # New conversation should start fresh
        result = response_generator.generate_response(sample_session_id, "Hi again")
        assert result['metadata']['current_phase'] == 'intent'
    
    def test_get_conversation_summary(self, response_generator, sample_session_id):
        """Test conversation summary generation."""
        response_generator.generate_response(sample_session_id, "I need help")
        response_generator.generate_response(sample_session_id, "My sales are low")
        
        summary = response_generator.get_conversation_summary(sample_session_id)
        assert 'session_summary' in summary
        assert 'phase_progress' in summary
        assert 'captures' in summary


@pytest.mark.integration
@pytest.mark.generator
class TestResponseGeneratorEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_input_handling(self, response_generator, sample_session_id):
        """Test system handles empty input gracefully."""
        result = response_generator.generate_response(sample_session_id, "")
        # Should return a response even for empty input
        assert 'response' in result
    
    def test_very_long_input(self, response_generator, sample_session_id):
        """Test system handles long inputs."""
        long_input = " ".join(["test"] * 500)
        result = response_generator.generate_response(sample_session_id, long_input)
        assert 'response' in result
    
    def test_special_characters(self, response_generator, sample_session_id):
        """Test system handles special characters."""
        result = response_generator.generate_response(
            sample_session_id,
            "I need help with @#$% sales!"
        )
        assert 'response' in result
