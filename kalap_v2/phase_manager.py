from typing import Dict

class PhaseManager:
    PHASES = ['intent', 'problem', 'solution', 'value', 'objection', 'close']

    def __init__(self):
        self.phases = self.PHASES

    def get_current_phase(self, session_id: str, context_tracker) -> str:
        context = context_tracker.get_context(session_id)
        return context.get('current_phase', 'intent')

    def advance_phase(self, session_id: str, context_tracker) -> str:
        current = self.get_current_phase(session_id, context_tracker)
        try:
            idx = self.phases.index(current)
            if idx < len(self.phases) - 1:
                new_phase = self.phases[idx + 1]
                context_tracker.get_context(session_id)['current_phase'] = new_phase
                return new_phase
        except (ValueError, IndexError):
            pass
        return current

    def can_advance_phase(self, session_id: str, completion_scores: Dict[str, float], context_tracker) -> bool:
        if not completion_scores:
            return False
        avg_score = sum(completion_scores.values()) / len(completion_scores)
        return avg_score >= 0.2
