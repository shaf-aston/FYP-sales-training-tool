"""Unit tests for phase_manager.py - Phase transitions and gate validation."""

import pytest


@pytest.mark.unit
@pytest.mark.phase
@pytest.mark.fast
class TestPhaseManagerBasics:
    """Test basic phase management."""
    
    def test_get_current_phase_default(self, phase_manager, context_tracker, sample_session_id):
        """Test default phase is 'intent'."""
        current = phase_manager.get_current_phase(sample_session_id, context_tracker)
        assert current == 'intent'
    
    def test_get_required_captures_for_phase(self, phase_manager):
        """Test required captures retrieval for a phase."""
        captures = phase_manager.get_required_captures('intent')
        assert isinstance(captures, list)
        assert len(captures) > 0


@pytest.mark.unit
@pytest.mark.phase
@pytest.mark.fast
class TestPhaseManagerTransitions:
    """Test phase transition logic."""
    
    def test_cannot_advance_without_captures(self, phase_manager, context_tracker, sample_session_id):
        """Test phase gate blocks advancement without required captures."""
        can_advance = phase_manager.can_advance_phase(
            sample_session_id,
            {},  # No completion scores
            context_tracker
        )
        assert can_advance is False
    
    def test_can_advance_with_sufficient_scores(self, phase_manager, context_tracker, sample_session_id):
        """Test phase advancement allowed with sufficient scores."""
        # Get required captures and set high scores
        required = phase_manager.get_required_captures('intent')
        scores = {cap: 0.8 for cap in required}
        
        can_advance = phase_manager.can_advance_phase(
            sample_session_id,
            scores,
            context_tracker
        )
        assert can_advance is True
    
    def test_advance_phase_updates_context(self, phase_manager, context_tracker, sample_session_id):
        """Test advance_phase updates context_tracker."""
        # Set sufficient scores
        context = context_tracker.get_context(sample_session_id)
        context['current_phase'] = 'intent'
        required = phase_manager.get_required_captures('intent')
        for cap in required:
            context_tracker.set_capture(sample_session_id, cap, 'test_value', 0.9)
        
        new_phase = phase_manager.advance_phase(sample_session_id, context_tracker)
        updated_context = context_tracker.get_context(sample_session_id)
        assert updated_context['current_phase'] == new_phase
        assert new_phase != 'intent'


@pytest.mark.unit
@pytest.mark.phase
@pytest.mark.fast
class TestPhaseManagerProgress:
    """Test progress tracking."""
    
    def test_get_phase_progress(self, phase_manager, context_tracker, sample_session_id):
        """Test phase progress calculation."""
        progress = phase_manager.get_phase_progress(sample_session_id, context_tracker)
        assert 'current_phase' in progress
        assert 'progress_percentage' in progress
        assert 0 <= progress['progress_percentage'] <= 100
    
    def test_progress_increases_with_captures(self, phase_manager, context_tracker, sample_session_id):
        """Test progress percentage increases as captures are made."""
        initial_progress = phase_manager.get_phase_progress(sample_session_id, context_tracker)
        
        # Add a capture
        context_tracker.set_capture(sample_session_id, 'tangible_outcome', 'test', 0.7)
        
        updated_progress = phase_manager.get_phase_progress(sample_session_id, context_tracker)
        assert updated_progress['progress_percentage'] >= initial_progress['progress_percentage']


@pytest.mark.unit
@pytest.mark.phase
@pytest.mark.fast
class TestPhaseManagerReset:
    """Test session reset functionality."""
    
    def test_reset_session(self, phase_manager, context_tracker, sample_session_id):
        """Test reset_session clears phase data."""
        # Advance phase
        context = context_tracker.get_context(sample_session_id)
        context['current_phase'] = 'pitch'
        
        # Reset
        phase_manager.reset_session(sample_session_id, context_tracker)
        
        # Verify reset to default
        current = phase_manager.get_current_phase(sample_session_id, context_tracker)
        assert current == 'intent'
