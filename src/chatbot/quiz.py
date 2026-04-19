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
    questions = _load_quiz_config().get("questions", {})
    normalized_type = quiz_type.replace("-", "_").lower()
    type_questions = questions.get(normalized_type, [])
    
    if type_questions:
        return random.choice(type_questions)
    
    fallbacks = {
        "stage": "What stage and strategy are we currently in?",
        "next_move": "What would you say next to this customer?",
        "direction": "Where are you taking this conversation and why?",
    }
    return fallbacks.get(normalized_type, "How would you proceed?")


def evaluate_stage_quiz(user_answer: str, bot: Any) -> dict:
    """Deterministic: did the user correctly ID the current stage and strategy?"""
    expected_stage = bot.flow_engine.current_stage
    expected_strategy = bot.flow_engine.flow_type
    answer_lower = user_answer.strip().lower()
    
    stage_ok = contains_nonnegated_keyword(answer_lower, expected_stage.lower())
    strategy_ok = contains_nonnegated_keyword(answer_lower, expected_strategy.lower())
    correct = stage_ok and strategy_ok
    
    # Build feedback based on what user got right
    if correct:
        feedback = f"Right — {expected_stage.upper()}, {expected_strategy.upper()} strategy."
    elif not stage_ok and not strategy_ok:
        feedback = f"Close, but not quite — it's {expected_stage.upper()} stage, {expected_strategy.upper()} strategy."
    elif not stage_ok:
        feedback = f"Strategy's right ({expected_strategy.upper()}), but you're in {expected_stage.upper()} stage now."
    else:
        feedback = f"Stage is right ({expected_stage.upper()}), but this is {expected_strategy.upper()} strategy."
    
    return {
        "correct": correct,
        "score": 1 if correct else 0,
        "user_answer": user_answer,
        "expected": {"stage": expected_stage, "strategy": expected_strategy},
        "feedback": feedback,
    }


def evaluate_next_move_quiz(user_response: str, bot: Any, last_user_message: str = "") -> dict:
    """LLM-scored: how well does the proposed response fit the current stage?"""
    stage, strategy = bot.flow_engine.current_stage, bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)
    
    eval_prompt = f"""You're grading a sales trainee's proposed response.
Context: Stage: {stage} | Strategy: {strategy}
Stage goal: {rubric["goal"]}
Key concepts: {", ".join(rubric.get("key_concepts", []))}

Customer: "{last_user_message}"
Trainee's response: "{user_response}"

Evaluate: (1) Fits stage goal? (2) Right technique? (3) Natural/not robotic? (4) Premature pitch or fatigue?

Return JSON: {"score": <0-100>, "alignment": "<strong|partial|weak>", "feedback": "<2-3 sentences>", "strengths": ["..."], "improvements": ["..."]}"""
    
    return _evaluate_with_llm(bot, eval_prompt, "Evaluate the trainee's response.", 
                              {"alignment": _ALIGNMENT_VALUES, "feedback": "Unable to evaluate response.", 
                               "strengths": [], "improvements": []}, "score_quiz_response")


def _evaluate_with_llm(bot: Any, system_prompt: str, user_msg: str, field_defaults: dict, error_context: str) -> dict:
    """Shared LLM evaluation: tries to extract JSON, falls back to sensible defaults."""
    try:
        response = bot.provider.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_msg}],
            temperature=0.3, max_tokens=300
        )
        result = extract_json_from_llm(response.content) if response.content else None
        if not result:
            raise ValueError("Empty JSON")
        
        # Validate enums if provided
        for field, valid_set in [(k, v) for k, v in field_defaults.items() if isinstance(v, set)]:
            if field in result and result[field] not in valid_set:
                result[field] = next(iter(valid_set))  # Use first valid value
        
        return {k: result.get(k, v) for k, v in field_defaults.items() if not isinstance(v, set)}
    except Exception as e:
        logger.warning(f"LLM evaluation failed ({error_context}): {e}")
        return field_defaults


def evaluate_direction_quiz(user_explanation: str, bot: Any) -> dict:
    """LLM-scored: does the trainee understand where the conversation is headed?"""
    stage, strategy = bot.flow_engine.current_stage, bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)
    
    eval_prompt = f"""Check if trainee understands conversation direction.
Stage: {stage} | Strategy: {strategy}
Goal: {rubric["goal"]} | Advance when: {rubric["advance_when"]}
Next: {rubric.get("next_stage", "end")} | Concepts: {", ".join(rubric.get("key_concepts", []))}

Trainee said: "{user_explanation}"

Do they understand: (1) Stage goal? (2) Advancement trigger? (3) Conversation flow?
Return JSON: {"score": <0-100>, "understanding": "<excellent|good|partial|needs_work>", "feedback": "<2-3 sentences>", "key_concepts_got": ["..."], "key_concepts_missed": ["..."]}"""
    
    result = _evaluate_with_llm(bot, eval_prompt, "Evaluate understanding.",
                               {"score": None, "understanding": "unknown", "feedback": "Couldn't score that one.",
                                "key_concepts_got": [], "key_concepts_missed": [], 
                                "valid_understanding": _UNDERSTANDING_VALUES}, "direction_quiz")
    
    understanding = result.get("understanding")
    if understanding not in _UNDERSTANDING_VALUES:
        understanding = "partial"
    
    return {
        "score": clamp_score(result.get("score", 50)) if result.get("score") else None,
        "understanding": understanding,
        "feedback": result.get("feedback", "Unable to evaluate."),
        "key_concepts_got": result.get("key_concepts_got", []),
        "key_concepts_missed": result.get("key_concepts_missed", []),
    }
