"""Quiz assessment: stage ID (deterministic), next-move and direction (LLM-scored)"""

import logging
import random
from typing import Any

from .loader import load_yaml
from .utils import clamp_score, contains_nonnegated_keyword, extract_json_from_llm

logger = logging.getLogger(__name__)

_quiz_config = None

# valid enums; anything else falls back
_ALIGNMENT_VALUES = {"strong", "partial", "weak"}
_UNDERSTANDING_VALUES = {"excellent", "good", "partial", "needs_work"}


def _load_quiz_config() -> dict:
    """Load quiz configuration (cached)"""
    global _quiz_config
    if _quiz_config is None:
        _quiz_config = load_yaml("quiz_config.yaml")
    return _quiz_config


def get_stage_rubric(stage: str, strategy: str) -> dict:
    """Rubric for a stage/strategy combo: goal, advance_when, key_concepts, next_stage"""
    config = _load_quiz_config()
    stages = config.get("stages", {})

    lookup_strategy = "consultative" if strategy == "intent" else strategy

    strategy_stages = stages.get(lookup_strategy, {})
    rubric = strategy_stages.get(stage, None)

    if rubric is None:
        return {
            "goal": f"Complete the {stage} stage",
            "advance_when": "Stage objectives are met",
            "key_concepts": ["Listen actively", "Ask relevant questions"],
            "next_stage": None,
        }

    return rubric


def get_quiz_question(quiz_type: str) -> str:
    """Pick a random question for the given quiz type"""
    config = _load_quiz_config()
    questions = config.get("questions", {})

    normalized_type = quiz_type.replace("-", "_").lower()
    type_questions = questions.get(normalized_type, [])

    if not type_questions:
        fallbacks = {
            "stage": "What stage and strategy are we currently in?",
            "next_move": "What would you say next to this customer?",
            "direction": "Where are you taking this conversation and why?",
        }
        return fallbacks.get(normalized_type, "How would you proceed?")

    return random.choice(type_questions)


# Use central contains_nonnegated_keyword from utils


def evaluate_stage_quiz(user_answer: str, bot: Any) -> dict:
    """Deterministic: did the user correctly ID the current stage and strategy?"""
    expected_stage = bot.flow_engine.current_stage
    expected_strategy = bot.flow_engine.flow_type

    answer_lower = user_answer.strip().lower()
    stage_correct = contains_nonnegated_keyword(answer_lower, expected_stage.lower())
    strategy_correct = contains_nonnegated_keyword(
        answer_lower, expected_strategy.lower()
    )
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
    """Generate feedback for stage quiz answer"""
    if correct:
        return f"Right — {stage.upper()}, {strategy.upper()} strategy."

    if not stage_correct and not strategy_correct:
        return f"Close, but not quite — it's {stage.upper()} stage, {strategy.upper()} strategy."
    elif not stage_correct:
        return f"Strategy's right ({strategy.upper()}), but you're in {stage.upper()} stage now."
    else:
        return f"Stage is right ({stage.upper()}), but this is {strategy.upper()} strategy."


def evaluate_next_move_quiz(
    user_response: str,
    bot: Any,
    last_user_message: str = "",
) -> dict:
    """LLM-scored: how well does the proposed response fit the current stage?"""
    stage = bot.flow_engine.current_stage
    strategy = bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)

    eval_prompt = f"""You're grading a sales trainee's proposed response.

Context:
- Stage: {stage}
- Strategy: {strategy}
- Stage goal: {rubric["goal"]}
- Key concepts for this stage: {", ".join(rubric.get("key_concepts", []))}

Customer's last message:
"{last_user_message}"

Trainee's proposed response:
"{user_response}"

What to look for:
1. Does this fit what the stage is trying to do?
2. Are they using the right technique here?
3. Does it sound natural, not robotic?
4. Are they pitching too early, or asking too many questions?

Return your evaluation as JSON:
{{
    "score": <0-100>,
    "alignment": "<strong|partial|weak>",
    "feedback": "<2-3 sentences of feedback>",
    "strengths": ["<what they did well>"],
    "improvements": ["<specific suggestions>"]
}}"""

    try:
        messages = [
            {"role": "system", "content": eval_prompt},
            {"role": "user", "content": "Evaluate the trainee's response."},
        ]

        response = bot.provider.chat(messages, temperature=0.3, max_tokens=300)

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
    except Exception as e:
        logger.warning(f"Failed to evaluate stage quiz response: {e}")

    return {
        "score": None,
        "alignment": "unknown",
        "feedback": "Couldn't score that one — answer saved, try the next question.",
        "strengths": [],
        "improvements": [],
    }


def evaluate_direction_quiz(user_explanation: str, bot: Any) -> dict:
    """LLM-scored: does the trainee understand where the conversation is headed?"""
    stage = bot.flow_engine.current_stage
    strategy = bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)

    eval_prompt = f"""You're checking whether the trainee knows where the conversation is going.

Current state:
- Stage: {stage}
- Strategy: {strategy}
- Stage goal: {rubric["goal"]}
- Advancement trigger: {rubric["advance_when"]}
- Next stage: {rubric.get("next_stage", "conversation end")}

Key concepts to check:
{rubric.get("key_concepts", ["Active listening", "Customer focus"])}

Trainee's explanation:
"{user_explanation}"

Check whether they understand:
1. What they're trying to do in this stage
2. What would tell them it's time to move to the next stage
3. How this fits into the wider sales conversation

Return your evaluation as JSON:
{{
    "score": <0-100>,
    "understanding": "<excellent|good|partial|needs_work>",
    "feedback": "<2-3 sentences of feedback>",
    "key_concepts_got": ["<concepts they demonstrated>"],
    "key_concepts_missed": ["<concepts they should have mentioned>"]
}}"""

    try:
        messages = [
            {"role": "system", "content": eval_prompt},
            {"role": "user", "content": "Evaluate understanding."},
        ]

        response = bot.provider.chat(messages, temperature=0.3, max_tokens=300)

        result = extract_json_from_llm(response.content)
        if result:
            understanding = result.get("understanding")
            return {
                "score": clamp_score(result.get("score", 50)),
                "understanding": understanding
                if understanding in _UNDERSTANDING_VALUES
                else "partial",
                "feedback": result.get("feedback", "Unable to evaluate."),
                "key_concepts_got": result.get("key_concepts_got", []),
                "key_concepts_missed": result.get("key_concepts_missed", []),
            }
    except Exception as e:
        logger.warning(f"Failed to evaluate direction quiz: {e}")

    return {
        "score": None,
        "understanding": "unknown",
        "feedback": "Couldn't score that one — explanation saved, try the next question.",
        "key_concepts_got": [],
        "key_concepts_missed": [],
    }
