"""
Question routing module for strategic question selection.
Handles context-aware question generation and template rendering.
"""

from typing import Dict, Optional
from .phase_manager import PhaseManager
from .context_tracker import ContextTracker
from .answer_validator import AnswerValidator


class QuestionRouter:
    """Routes and formats questions based on phase and context."""
    
    # Opening questions for each phase
    OPENING_QUESTIONS = {
        'intent': 'What specifically are you looking to achieve?',
        'problem': 'What challenges are you currently facing?',
        'solution': 'What solutions have you considered so far?',
        'value': 'What would success look like for you?',
        'objection': 'What concerns or questions do you have?',
        'close': 'Are you ready to move forward with this?'
    }
    
    # Probe questions by type
    PROBE_QUESTIONS = {
        'intent': {
            'emotion': 'How does this situation make you feel?',
            'specificity': 'Can you give me a specific example?',
            'timeline': 'When do you need to achieve this by?',
            'impact': 'How is this affecting your business?'
        },
        'problem': {
            'emotion': 'How long has this been bothering you?',
            'specificity': 'Can you quantify the impact?',
            'timeline': 'When did this problem start?',
            'impact': 'What has this cost you so far?'
        },
        'solution': {
            'emotion': 'What excites you most about solving this?',
            'specificity': 'What specific features matter most?',
            'timeline': "What's your ideal implementation timeline?",
            'impact': 'What results are you expecting?'
        },
        'value': {
            'emotion': 'Why is this important to you personally?',
            'specificity': 'What metrics will you use to measure success?',
            'timeline': 'When do you need to see results?',
            'impact': 'How will this change your day-to-day?'
        },
        'objection': {
            'emotion': "What's your biggest concern?",
            'specificity': 'Can you elaborate on that?',
            'timeline': 'What would make you comfortable moving forward?',
            'impact': "What would happen if you don't address this?"
        },
        'close': {
            'emotion': 'How are you feeling about this?',
            'specificity': 'What final details do you need?',
            'timeline': 'When would you like to start?',
            'impact': 'What are the next steps for you?'
        }
    }
    
    def __init__(
        self, 
        phase_manager: PhaseManager, 
        context_tracker: ContextTracker,
        answer_validator: AnswerValidator
    ):
        """
        Initialize question router.
        
        Args:
            phase_manager: Phase management instance
            context_tracker: Context tracking instance
            answer_validator: Answer validation instance
        """
        self.phase_manager = phase_manager
        self.context_tracker = context_tracker
        self.answer_validator = answer_validator
    
    def get_opening_question(self, phase: str) -> str:
        """
        Get opening question for a phase.
        
        Args:
            phase: Current phase name
            
        Returns:
            Opening question string
        """
        return self.OPENING_QUESTIONS.get(phase, 'Tell me more.')
    
    def get_probe_question(self, phase: str, probe_type: str = 'specificity') -> str:
        """
        Get a probe question for deeper exploration.
        
        Args:
            phase: Current phase name
            probe_type: Type of probe ('emotion', 'specificity', 'timeline', 'impact')
            
        Returns:
            Probe question string
        """
        phase_probes = self.PROBE_QUESTIONS.get(phase, {})
        return phase_probes.get(probe_type, 'Can you tell me more about that?')
    
    def format_question_with_context(
        self, 
        question: str, 
        session_id: str
    ) -> str:
        """
        Format question with context variables.
        
        Args:
            question: Question template with {variable} placeholders
            session_id: Session identifier
            
        Returns:
            Formatted question with variables replaced
        """
        context = self.context_tracker.get_context(session_id)
        captures = context.get('captures', {})
        
        # Simple variable replacement
        formatted = question
        for key, value in captures.items():
            placeholder = f"{{{key}}}"
            if placeholder in formatted:
                formatted = formatted.replace(placeholder, str(value))
        
        return formatted
    
    def should_probe_deeper(
        self, 
        session_id: str, 
        user_input: str, 
        capture_key: str
    ) -> bool:
        """
        Determine if we should probe deeper based on answer quality.
        
        Args:
            session_id: Session identifier
            user_input: User's response
            capture_key: Key being captured
            
        Returns:
            True if should probe deeper, False otherwise
        """
        # Use answer validator to check if response is sufficient
        context = self.context_tracker.get_context(session_id)
        phase = context.get('current_phase', 'intent')
        
        validation = self.answer_validator.validate(user_input, capture_key, phase)
        
        # Probe if answer is insufficient
        return not validation.get('sufficient', False)
    
    def get_next_question(
        self, 
        session_id: str, 
        user_input: Optional[str] = None
    ) -> str:
        """
        Get the next appropriate question based on context.
        
        Args:
            session_id: Session identifier
            user_input: Optional user input to consider
            
        Returns:
            Next question to ask
        """
        context = self.context_tracker.get_context(session_id)
        current_phase = context.get('current_phase', 'intent')
        captures = context.get('captures', {})
        
        # If we have user input, check if we need to probe
        if user_input:
            # Determine what we're trying to capture in this phase
            capture_key = current_phase  # Simplified - use phase as capture key
            
            if self.should_probe_deeper(session_id, user_input, capture_key):
                # Return a probe question
                return self.get_probe_question(current_phase, 'specificity')
        
        # Otherwise, return opening question for current phase
        question = self.get_opening_question(current_phase)
        
        # Format with context if needed
        return self.format_question_with_context(question, session_id)
