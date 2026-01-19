from typing import Dict, Any
from .context_tracker import ContextTracker

PHASES = ['intent', 'problem', 'solution', 'value', 'objection', 'close']

QUESTIONS = {
    'intent': 'What is your main goal?',
    'problem': 'What problems are you facing?',
    'solution': 'What solutions have you considered?',
    'value': 'What value matters most to you?',
    'objection': 'What concerns do you have?',
    'close': 'Are you ready to move forward?'
}

class ResponseGenerator:
    def __init__(self):
        self.context_tracker = ContextTracker()
        self.phases = PHASES

    def _score_answer(self, text: str) -> float:
        words = len(text.split())
        has_numbers = any(c.isdigit() for c in text)
        score = min(words / 10.0, 0.8)
        return min(score + (0.2 if has_numbers else 0), 1.0)

    def _advance_phase(self, session_id: str) -> str:
        ctx = self.context_tracker.get_context(session_id)
        current = ctx.get('current_phase', 'intent')

        try:
            idx = self.phases.index(current)
            if idx < len(self.phases) - 1:
                new_phase = self.phases[idx + 1]
                ctx['current_phase'] = new_phase
                return new_phase
        except (ValueError, IndexError):
            pass
        return current

    def generate_response(self, session_id: str, user_input: str) -> Dict[str, Any]:
        ctx = self.context_tracker.get_context(session_id)
        current_phase = ctx.get('current_phase', 'intent')

        self.context_tracker.add_message(session_id, 'user', user_input)

        word_count = len(user_input.split())
        if word_count >= 2:
            score = self._score_answer(user_input)
            self.context_tracker.set_capture(session_id, current_phase, user_input, score)

            scores = self.context_tracker.get_all_completion_scores(session_id)
            avg = sum(scores.values()) / len(scores) if scores else 0

            if avg >= 0.2:
                new_phase = self._advance_phase(session_id)
                response_text = f"Great! Now: {QUESTIONS.get(new_phase, 'Continue?')}"
            else:
                response_text = f"Got it. {QUESTIONS.get(current_phase, 'Continue?')}"
        else:
            response_text = f"Please provide more detail. {QUESTIONS.get(current_phase, 'Try again?')}"

        self.context_tracker.add_message(session_id, 'assistant', response_text)

        return {
            "response": response_text,
            "phase": ctx.get('current_phase', 'intent'),
            "metadata": {
                "session_id": session_id,
                "completion_scores": self.context_tracker.get_all_completion_scores(session_id)
            }
        }

    def reset_conversation(self, session_id: str):
        self.context_tracker.clear_session(session_id)
