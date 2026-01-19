from typing import Dict, Any, Optional

class ContextTracker:
    def __init__(self):
        self.sessions = {}

    def get_context(self, session_id: str) -> Dict[str, Any]:
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'current_phase': 'intent',
                'conversation_history': [],
                'captures': {},
                'completion_scores': {}
            }
        return self.sessions[session_id]

    def add_message(self, session_id: str, role: str, message: str):
        context = self.get_context(session_id)
        context['conversation_history'].append({
            'role': role,
            'message': message
        })

    def set_capture(self, session_id: str, capture_key: str, value: str, score: float = 0.0):
        context = self.get_context(session_id)
        context['captures'][capture_key] = value
        context['completion_scores'][capture_key] = score

    def get_capture(self, session_id: str, capture_key: str) -> Optional[str]:
        return self.get_context(session_id)['captures'].get(capture_key)

    def get_completion_score(self, session_id: str, capture_key: str) -> float:
        return self.get_context(session_id)['completion_scores'].get(capture_key, 0.0)

    def get_all_completion_scores(self, session_id: str) -> Dict[str, float]:
        return self.get_context(session_id)['completion_scores'].copy()

    def get_conversation_history(self, session_id: str) -> list:
        return self.get_context(session_id)['conversation_history'].copy()

    def clear_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
