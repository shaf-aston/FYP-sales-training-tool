"""Unit tests for context_tracker.py - Session state management."""

import pytest


@pytest.mark.unit
@pytest.mark.context
@pytest.mark.fast
class TestContextTrackerSession:
    """Test session creation and retrieval."""
    
    def test_create_new_session(self, context_tracker, sample_session_id):
        """Test new session creation with default structure."""
        context = context_tracker.get_context(sample_session_id)
        assert context['current_phase'] == 'intent'
        assert context['conversation_history'] == []
        assert context['captures'] == {}
        assert context['completion_scores'] == {}
    
    def test_session_persistence_in_memory(self, context_tracker, sample_session_id):
        """Test session persists across get_context calls."""
        context1 = context_tracker.get_context(sample_session_id)
        context1['current_phase'] = 'logical_certainty'
        context2 = context_tracker.get_context(sample_session_id)
        assert context2['current_phase'] == 'logical_certainty'
    
    def test_multiple_sessions_isolated(self, context_tracker):
        """Test multiple sessions don't interfere."""
        session1 = context_tracker.get_context("session-1")
        session2 = context_tracker.get_context("session-2")
        session1['current_phase'] = 'pitch'
        assert session2['current_phase'] == 'intent'
    
    def test_session_exists(self, context_tracker, sample_session_id):
        """Test session existence check."""
        assert not context_tracker.session_exists(sample_session_id)
        context_tracker.get_context(sample_session_id)
        assert context_tracker.session_exists(sample_session_id)


@pytest.mark.unit
@pytest.mark.context
@pytest.mark.fast
class TestContextTrackerMessages:
    """Test message history management."""
    
    def test_add_message(self, context_tracker, sample_session_id):
        """Test adding messages to conversation history."""
        context_tracker.add_message(sample_session_id, 'user', 'Hello')
        history = context_tracker.get_conversation_history(sample_session_id)
        assert len(history) == 1
        assert history[0]['role'] == 'user'
        assert history[0]['message'] == 'Hello'
    
    def test_message_timestamp(self, context_tracker, sample_session_id):
        """Test messages include timestamps."""
        context_tracker.add_message(sample_session_id, 'assistant', 'Hi')
        history = context_tracker.get_conversation_history(sample_session_id)
        assert 'timestamp' in history[0]
    
    def test_get_last_n_messages(self, context_tracker, sample_session_id):
        """Test retrieving last N messages."""
        for i in range(5):
            context_tracker.add_message(sample_session_id, 'user', f'Message {i}')
        recent = context_tracker.get_conversation_history(sample_session_id, last_n=2)
        assert len(recent) == 2
        assert recent[-1]['message'] == 'Message 4'


@pytest.mark.unit
@pytest.mark.context
@pytest.mark.fast
class TestContextTrackerCaptures:
    """Test data capture management."""
    
    def test_set_capture(self, context_tracker, sample_session_id):
        """Test setting captured data."""
        context_tracker.set_capture(sample_session_id, 'budget', '50000', score=0.8)
        captured = context_tracker.get_capture(sample_session_id, 'budget')
        assert captured == '50000'
    
    def test_capture_with_score(self, context_tracker, sample_session_id):
        """Test captures store quality scores."""
        context_tracker.set_capture(sample_session_id, 'timeline', '3 months', score=0.75)
        score = context_tracker.get_completion_score(sample_session_id, 'timeline')
        assert score == 0.75
    
    def test_get_all_completion_scores(self, context_tracker, sample_session_id):
        """Test retrieving all completion scores."""
        context_tracker.set_capture(sample_session_id, 'cap1', 'val1', score=0.5)
        context_tracker.set_capture(sample_session_id, 'cap2', 'val2', score=0.9)
        scores = context_tracker.get_all_completion_scores(sample_session_id)
        assert len(scores) == 2
        assert scores['cap1'] == 0.5
        assert scores['cap2'] == 0.9


@pytest.mark.unit
@pytest.mark.context
@pytest.mark.fast
class TestContextTrackerProbes:
    """Test probe counting functionality."""
    
    def test_increment_probe_count(self, context_tracker, sample_session_id):
        """Test probe counter increments."""
        count1 = context_tracker.increment_probe_count(sample_session_id, 'budget')
        count2 = context_tracker.increment_probe_count(sample_session_id, 'budget')
        assert count1 == 1
        assert count2 == 2
    
    def test_get_probe_count(self, context_tracker, sample_session_id):
        """Test retrieving probe count."""
        context_tracker.increment_probe_count(sample_session_id, 'timeline')
        count = context_tracker.get_probe_count(sample_session_id, 'timeline')
        assert count == 1


@pytest.mark.unit
@pytest.mark.context
@pytest.mark.fast
class TestContextTrackerMetadata:
    """Test emotional hooks, pain points, and objections."""
    
    def test_add_emotional_hook(self, context_tracker, sample_session_id):
        """Test adding emotional hooks."""
        context = context_tracker.get_context(sample_session_id)
        context_tracker.add_emotional_hook(sample_session_id, "wants to prove worth")
        assert "wants to prove worth" in context['emotional_hooks']
    
    def test_add_pain_point(self, context_tracker, sample_session_id):
        """Test adding pain points."""
        context_tracker.add_pain_point(sample_session_id, "low conversion rate")
        context = context_tracker.get_context(sample_session_id)
        assert "low conversion rate" in context['pain_points']
    
    def test_add_objection_signal(self, context_tracker, sample_session_id):
        """Test adding objection signals."""
        context_tracker.add_objection_signal(sample_session_id, 'price_sensitivity', 'too expensive')
        context = context_tracker.get_context(sample_session_id)
        assert len(context['objection_signals']) == 1
        assert context['objection_signals'][0]['type'] == 'price_sensitivity'
    
    def test_update_commitment_temperature(self, context_tracker, sample_session_id):
        """Test commitment temperature bounds (0-1)."""
        context_tracker.update_commitment_temperature(sample_session_id, 0.7)
        context = context_tracker.get_context(sample_session_id)
        assert context['commitment_temperature'] == 0.7
        
        # Test bounds
        context_tracker.update_commitment_temperature(sample_session_id, 1.5)
        assert context_tracker.get_context(sample_session_id)['commitment_temperature'] == 1.0


@pytest.mark.unit
@pytest.mark.context
@pytest.mark.fast
class TestContextTrackerCleanup:
    """Test session cleanup operations."""
    
    def test_clear_session(self, context_tracker, sample_session_id):
        """Test session deletion."""
        context_tracker.get_context(sample_session_id)
        assert context_tracker.session_exists(sample_session_id)
        context_tracker.clear_session(sample_session_id)
        assert not context_tracker.session_exists(sample_session_id)
    
    def test_get_session_summary(self, context_tracker, sample_session_id):
        """Test session summary generation."""
        context_tracker.add_message(sample_session_id, 'user', 'test')
        context_tracker.set_capture(sample_session_id, 'test', 'val', 0.8)
        summary = context_tracker.get_session_summary(sample_session_id)
        assert summary['message_count'] == 1
        assert summary['captures_count'] == 1
        assert 'average_completion' in summary
