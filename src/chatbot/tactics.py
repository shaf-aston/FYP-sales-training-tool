"""Adaptive tactical guidance based on user state."""

from typing import Any
from .loader import get_adaptation_template, get_tactic
from .analysis import is_literal_question

def build_tactic_guidance(strategy: str, state: Any, user_message: str) -> str:
    """Build adaptive tactic guidance based on user state and strategy.

    Returns guidance string for: decisive users, literal questions, low-intent/guarded users.
    """
    if state.decisive:
        return get_adaptation_template("decisive_user", strategy=strategy)

    if state.intent == "low" or state.guarded or state.question_fatigue:
        if is_literal_question(user_message):
            return get_adaptation_template("literal_question")

        # Determine reason for adaptation
        if state.intent == "low":
            reason = "low intent"
        elif state.guarded:
            reason = "guarded response"
        else:
            reason = "question fatigue (2+ recent questions)"
        
        # Get elicitation example if consultative
        elicitation_example = ""
        if strategy == "consultative":
            elicitation_example = get_tactic("elicitation", "combined")
        
        return get_adaptation_template(
            "low_intent_guarded",
            strategy=strategy,
            reason=reason,
            elicitation_example=elicitation_example
        )

    return ""
