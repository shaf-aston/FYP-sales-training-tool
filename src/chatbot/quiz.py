"""Quiz assessment: stage ID (deterministic), next-move and direction (LLM-scored)"""

import logging
import random
from typing import Any

from .loader import load_yaml
from .utils import clamp_score, contains_nonnegated_keyword, extract_json_from_llm

logger = logging.getLogger(__name__)
_quiz_config = None

# Valid enum sets for LLM field validation
_ENUMS = {
    "alignment": {"strong", "partial", "weak"},
    "understanding": {"excellent", "good", "partial", "needs_work"},
}


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
    
    return rubric or {
        "goal": f"Complete the {stage} stage",
        "advance_when": "Stage objectives are met",
        "key_concepts": ["Listen actively", "Ask relevant questions"],
        "next_stage": None,
    }


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


def test_quiz_stage_answer(user_answer: str, bot: Any) -> dict:
    """Deterministic: did the user correctly ID the current stage and strategy?

    Renamed from `test_quiz_stage` to make the purpose clearer in call sites
    and test names (`test_quiz_stage_answer`). Behavior is unchanged.
    """
    expected_stage = bot.flow_engine.current_stage
    expected_strategy = bot.flow_engine.flow_type
    answer_lower = user_answer.strip().lower()

    stage_ok = contains_nonnegated_keyword(answer_lower, expected_stage.lower())
    strategy_ok = contains_nonnegated_keyword(answer_lower, expected_strategy.lower())
    correct = stage_ok and strategy_ok

    # Build feedback based on what user got right
    feedback_map = {
        (True, True): f"Right — {expected_stage.upper()}, {expected_strategy.upper()} strategy.",
        (False, False): f"Close, but not quite — it's {expected_stage.upper()} stage, {expected_strategy.upper()} strategy.",
        (False, True): f"Strategy's right ({expected_strategy.upper()}), but you're in {expected_stage.upper()} stage now.",
        (True, False): f"Stage is right ({expected_stage.upper()}), but this is {expected_strategy.upper()} strategy.",
    }
    feedback = feedback_map[(stage_ok, strategy_ok)]

    return {
        "correct": correct,
        "score": 1 if correct else 0,
        "user_answer": user_answer,
        "expected": {"stage": expected_stage, "strategy": expected_strategy},
        "feedback": feedback,
    }


def test_quiz_next_move(user_response: str, bot: Any, last_user_message: str = "") -> dict:
    """LLM-scored: how well does the proposed response fit the current stage?"""
    stage, strategy = bot.flow_engine.current_stage, bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)
    concepts = ", ".join(rubric.get("key_concepts", []))
    
    prompt = f"""Grade trainee response in {stage} ({strategy}).
Goal: {rubric["goal"]} | Concepts: {concepts}
Customer: "{last_user_message}" | Response: "{user_response}"
JSON: {{"score": <0-100>, "alignment": "strong|partial|weak", "feedback": "<brief>", "strengths": ["..."], "improvements": ["..."]}}"""
    
    return _score_with_llm(bot, prompt, {
        "score": 50,
        "alignment": "partial",
        "feedback": "Unable to evaluate.",
        "strengths": [],
        "improvements": [],
    })


def test_quiz_direction(user_explanation: str, bot: Any) -> dict:
    """LLM-scored: does trainee understand conversation direction?"""
    stage, strategy = bot.flow_engine.current_stage, bot.flow_engine.flow_type
    rubric = get_stage_rubric(stage, strategy)
    concepts = ", ".join(rubric.get("key_concepts", []))
    
    prompt = f"""Evaluate trainee's understanding in {stage} ({strategy}).
Goal: {rubric["goal"]} | Advance: {rubric["advance_when"]} | Concepts: {concepts}
Trainee: "{user_explanation}"
JSON: {{"score": <0-100>, "understanding": "excellent|good|partial|needs_work", "feedback": "<brief>", "key_concepts_got": ["..."], "key_concepts_missed": ["..."]}}"""
    
    return _score_with_llm(bot, prompt, {
        "score": 50,
        "understanding": "partial",
        "feedback": "Unable to evaluate.",
        "key_concepts_got": [],
        "key_concepts_missed": [],
    })


def _score_with_llm(bot: Any, prompt: str, defaults: dict) -> dict:
    """Unified LLM scoring: validates enums, clamps scores, handles fallbacks."""
    try:
        response = bot.provider.chat([{"role": "system", "content": prompt}], temperature=0.3, max_tokens=300)
        result = extract_json_from_llm(response.content) if response.content else {}
        
        output = {}
        for key, default in defaults.items():
            val = result.get(key, default)
            # Validate enum fields
            if key in _ENUMS and isinstance(val, str) and val not in _ENUMS[key]:
                val = list(_ENUMS[key])[0]
            # Clamp numeric scores
            if key == "score" and isinstance(val, (int, float)):
                val = clamp_score(int(val))
            output[key] = val
        return output
    except Exception as e:
        logger.warning(f"LLM scoring failed: {e}")
        return defaults
