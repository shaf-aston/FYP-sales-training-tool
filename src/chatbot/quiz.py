"""Quiz Assessment Module - Evaluate trainee understanding of sales process.

Provides three quiz types:
1. Stage Quiz - Identify current stage and strategy (deterministic)
2. Next Move Quiz - Evaluate proposed response (LLM-based)
3. Direction Quiz - Assess strategic understanding (LLM-based)
"""
import random
from typing import Any

from .loader import load_yaml
from .utils import clamp_score, extract_json_from_llm


# =============================================================================
# Configuration Loading
# =============================================================================

_quiz_config = None

# Valid LLM output enums — anything outside these falls back to default
_ALIGNMENT_VALUES = {"strong", "partial", "weak"}
_UNDERSTANDING_VALUES = {"excellent", "good", "partial", "needs_work"}


def _load_quiz_config() -> dict:
    """Load quiz configuration (cached)."""
    global _quiz_config
    if _quiz_config is None:
        _quiz_config = load_yaml("quiz_config.yaml")
    return _quiz_config


def get_stage_rubric(stage: str, strategy: str) -> dict:
    """Get rubric for a specific stage/strategy combination.

    Args:
        stage: FSM stage name (intent, logical, emotional, pitch, objection)
        strategy: Strategy name (consultative, transactional, intent)

    Returns:
        dict with goal, advance_when, key_concepts, next_stage
    """
    config = _load_quiz_config()
    stages = config.get("stages", {})

    # Map "intent" strategy to consultative for rubric lookup
    lookup_strategy = "consultative" if strategy == "intent" else strategy

    strategy_stages = stages.get(lookup_strategy, {})
    rubric = strategy_stages.get(stage, None)

    if rubric is None:
        # Fallback rubric for unknown stages
        return {
            "goal": f"Complete the {stage} stage",
            "advance_when": "Stage objectives are met",
            "key_concepts": ["Listen actively", "Ask relevant questions"],
            "next_stage": None,
        }

    return rubric


def get_quiz_question(quiz_type: str) -> str:
    """Get a random quiz question for the specified type.

    Args:
        quiz_type: "stage", "next_move", or "direction"

    Returns:
        Question string
    """
    config = _load_quiz_config()
    questions = config.get("questions", {})

    # Normalize quiz type (allow underscore or hyphen)
    normalized_type = quiz_type.replace("-", "_").lower()

    type_questions = questions.get(normalized_type, [])

    if not type_questions:
        # Fallback questions
        fallbacks = {
            "stage": "What stage and strategy are we currently in?",
            "next_move": "What would you say next to this customer?",
            "direction": "Where are you taking this conversation and why?",
        }
        return fallbacks.get(normalized_type, "How would you proceed?")

    return random.choice(type_questions)


# =============================================================================
# Stage Quiz (Deterministic)
# =============================================================================

def evaluate_stage_quiz(user_answer: str, bot: Any) -> dict:
    """Evaluate stage identification quiz.

    This is a deterministic evaluation - user must identify both
    the current stage AND strategy correctly.

    Args:
        user_answer: User's free-text answer
        bot: SalesChatbot instance (or mock with flow_engine)

    Returns:
        {
            "correct": bool,
            "score": 0 or 1,
            "user_answer": str,
            "expected": {"stage": str, "strategy": str},
            "feedback": str
        }
    """
    expected_stage = bot.flow_engine.current_stage
    expected_strategy = bot.flow_engine.flow_type

    # Normalize answer for comparison
    answer_lower = user_answer.strip().lower()

    # Check for stage match (substring — no collision risk between stage names)
    stage_correct = expected_stage.lower() in answer_lower

    # Check for strategy match
    strategy_correct = expected_strategy.lower() in answer_lower

    # Both must be correct
    correct = stage_correct and strategy_correct

    feedback = _generate_stage_feedback(
        correct=correct,
        stage=expected_stage,
        strategy=expected_strategy,
        stage_correct=stage_correct,
        strategy_correct=strategy_correct,
    )

    return {
        "correct": correct,
        "score": 1 if correct else 0,
        "user_answer": user_answer,
        "expected": {"stage": expected_stage, "strategy": expected_strategy},
        "feedback": feedback,
    }


def _generate_stage_feedback(
    correct: bool,
    stage: str,
    strategy: str,
    stage_correct: bool,
    strategy_correct: bool,
) -> str:
    """Generate feedback for stage quiz answer."""
    if correct:
        return f"Correct! We're in the {stage.upper()} stage using {strategy.upper()} strategy."

    # Provide specific feedback on what was wrong
    if not stage_correct and not strategy_correct:
        return (
            f"Not quite. We're actually in the {stage.upper()} stage "
            f"using {strategy.upper()} strategy."
        )
    elif not stage_correct:
        return (
            f"Strategy is right, but not the stage. "
            f"We're in the {stage.upper()} stage ({strategy.upper()})."
        )
    else:
        return (
            f"Stage is right, but not the strategy. "
            f"We're using {strategy.upper()} ({stage.upper()} stage)."
        )


# =============================================================================
# Next Move Quiz (LLM-based)
# =============================================================================

def evaluate_next_move_quiz(
    user_response: str,
    bot: Any,
    last_user_message: str = "",
) -> dict:
    """Evaluate next move quiz using LLM comparison.

    Compares user's proposed response against stage objectives
    and NEPQ methodology.

    Args:
        user_response: User's proposed sales response
        bot: SalesChatbot instance with provider access
        last_user_message: The customer's last message

    Returns:
        {
            "score": 0-100,
            "alignment": "strong" | "partial" | "weak",
            "feedback": str,
            "strengths": [str],
            "improvements": [str]
        }
    """
    stage = bot.flow_engine.current_stage
    strategy = bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)

    # Build evaluation prompt
    eval_prompt = f"""You are evaluating a sales trainee's proposed response.

CONTEXT:
- Stage: {stage}
- Strategy: {strategy}
- Stage goal: {rubric['goal']}
- Key concepts for this stage: {', '.join(rubric.get('key_concepts', []))}

CUSTOMER'S LAST MESSAGE:
"{last_user_message}"

TRAINEE'S PROPOSED RESPONSE:
"{user_response}"

EVALUATION CRITERIA:
1. Does the response align with the stage goal?
2. Does it apply key concepts correctly?
3. Is it natural and customer-focused?
4. Does it avoid common mistakes (premature pitching, too many questions)?

Return your evaluation as JSON:
{{
    "score": <0-100>,
    "alignment": "<strong|partial|weak>",
    "feedback": "<2-3 sentence constructive feedback>",
    "strengths": ["<what they did well>"],
    "improvements": ["<specific suggestions>"]
}}"""

    try:
        messages = [
            {"role": "system", "content": eval_prompt},
            {"role": "user", "content": "Evaluate the trainee's response."},
        ]

        response = bot.provider.chat(messages, temperature=0.3, max_tokens=300)

        # Extract JSON from LLM response
        result = extract_json_from_llm(response.content)
        if result:
            alignment = result.get("alignment")
            return {
                "score": clamp_score(result.get("score", 50)),
                "alignment": alignment if alignment in _ALIGNMENT_VALUES else "partial",
                "feedback": result.get("feedback", "Unable to evaluate response."),
                "strengths": result.get("strengths", []),
                "improvements": result.get("improvements", []),
            }
    except Exception:
        pass  # Fall through to fallback

    # Fallback if LLM evaluation fails
    return {
        "score": 50,
        "alignment": "partial",
        "feedback": "Could not fully evaluate your response. Please try again.",
        "strengths": [],
        "improvements": ["Consider reviewing the stage objectives"],
    }


# =============================================================================
# Direction Quiz (LLM-based)
# =============================================================================

def evaluate_direction_quiz(user_explanation: str, bot: Any) -> dict:
    """Evaluate direction/strategy quiz using LLM.

    Tests whether the trainee understands:
    - Current stage goal
    - What triggers advancement
    - Overall conversation trajectory

    Args:
        user_explanation: User's explanation of their strategy
        bot: SalesChatbot instance

    Returns:
        {
            "score": 0-100,
            "understanding": "excellent" | "good" | "partial" | "needs_work",
            "feedback": str,
            "key_concepts_got": [str],
            "key_concepts_missed": [str]
        }
    """
    stage = bot.flow_engine.current_stage
    strategy = bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)

    eval_prompt = f"""You are evaluating a sales trainee's understanding of strategy.

CURRENT STATE:
- Stage: {stage}
- Strategy: {strategy}
- Stage goal: {rubric['goal']}
- Advancement trigger: {rubric['advance_when']}
- Next stage: {rubric.get('next_stage', 'conversation end')}

KEY CONCEPTS TO CHECK:
{rubric.get('key_concepts', ['Active listening', 'Customer focus'])}

TRAINEE'S EXPLANATION:
"{user_explanation}"

Evaluate whether the trainee understands:
1. What they're trying to achieve in this stage
2. What signals they're looking for to advance
3. How this fits into the overall sales process

Return your evaluation as JSON:
{{
    "score": <0-100>,
    "understanding": "<excellent|good|partial|needs_work>",
    "feedback": "<2-3 sentence constructive feedback>",
    "key_concepts_got": ["<concepts they demonstrated>"],
    "key_concepts_missed": ["<concepts they should have mentioned>"]
}}"""

    try:
        messages = [
            {"role": "system", "content": eval_prompt},
            {"role": "user", "content": "Evaluate understanding."},
        ]

        response = bot.provider.chat(messages, temperature=0.3, max_tokens=300)

        # Extract JSON from LLM response
        result = extract_json_from_llm(response.content)
        if result:
            understanding = result.get("understanding")
            return {
                "score": clamp_score(result.get("score", 50)),
                "understanding": understanding if understanding in _UNDERSTANDING_VALUES else "partial",
                "feedback": result.get("feedback", "Unable to evaluate."),
                "key_concepts_got": result.get("key_concepts_got", []),
                "key_concepts_missed": result.get("key_concepts_missed", []),
            }
    except Exception:
        pass  # Fall through to fallback

    # Fallback
    return {
        "score": 50,
        "understanding": "partial",
        "feedback": "Could not fully evaluate your explanation. Please try again.",
        "key_concepts_got": [],
        "key_concepts_missed": [],
    }
