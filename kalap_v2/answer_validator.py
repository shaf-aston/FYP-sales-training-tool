from typing import Dict, Any

class AnswerValidator:
    def __init__(self, scoring_rules_path: str = None, mode: str = "simple"):
        self.mode = mode

    def validate(self, user_input: str, capture_key: str, phase: str) -> Dict[str, Any]:
        word_count = len(user_input.split())

        if word_count < 2:
            return {
                "score": 0.0,
                "feedback": ["Answer too short"],
                "sufficient": False
            }

        score = min(word_count / 20.0, 1.0)
        return {
            "score": score,
            "feedback": [],
            "sufficient": word_count >= 2
        }

    def calculate_completion_score(self, user_input: str, capture_key: str) -> float:
        word_count = len(user_input.split())
        has_numbers = any(c.isdigit() for c in user_input)

        score = min(word_count / 10.0, 0.8)
        if has_numbers:
            score += 0.2

        return min(score, 1.0)
