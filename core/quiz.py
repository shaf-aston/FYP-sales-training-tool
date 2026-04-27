"""Quiz assessment: stage ID (deterministic), next-move and direction (hybrid-scored)."""

import logging
import random
import re
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

_STOPWORDS = {
    "and",
    "the",
    "that",
    "this",
    "with",
    "from",
    "into",
    "your",
    "their",
    "they",
    "them",
    "what",
    "when",
    "where",
    "which",
    "would",
    "should",
    "could",
    "about",
    "while",
    "there",
    "have",
    "been",
    "just",
    "only",
    "more",
    "less",
}

_OPEN_QUESTION_WORDS = ("what", "how", "why", "which", "where", "when", "who")


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric words."""
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _detect_concept_coverage(answer: str, concepts: list[str]) -> tuple[list[str], list[str]]:
    """Return (concepts_got, concepts_missed) using keyword overlap per concept."""
    answer_tokens = set(_tokenize(answer))
    matched_concepts, unmatched_concepts = [], []

    for concept in concepts:
        concept_tokens = [
            token
            for token in _tokenize(concept)
            if len(token) > 3 and token not in _STOPWORDS
        ]
        matched = bool(concept_tokens) and any(token in answer_tokens for token in concept_tokens)
        if matched:
            matched_concepts.append(concept)
        else:
            unmatched_concepts.append(concept)

    return matched_concepts, unmatched_concepts


def _alignment_from_score(score: int) -> str:
    """Map a numeric score to a coarse alignment label."""
    if score >= 75:
        return "strong"
    if score >= 45:
        return "partial"
    return "weak"


def _understanding_from_score(score: int) -> str:
    """Map a numeric score to a coarse understanding label."""
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 45:
        return "partial"
    return "needs_work"


def _merge_unique_items(*lists: list[str], max_items: int = 4) -> list[str]:
    """Merge list items in insertion order, removing duplicates and empty values.

    Stops after `max_items` so feedback lists stay short and readable. Earlier
    lists take priority when deduplication trims the final result.
    """
    seen = set()
    merged = []
    for items in lists:
        for item in items or []:
            text = str(item).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
            if len(merged) >= max_items:
                return merged
    return merged


def _build_coach_tip(missed_concepts: list[str], mode: str) -> str:
    """Create one clear coaching tip based on the highest-value missed concept."""
    if missed_concepts:
        return f"Focus next on this concept: {missed_concepts[0]}."
    if mode == "next_move":
        return "Keep one open question tied to the customer's last message."
    return "State the next step and why it moves the stage forward."


def _deterministic_open_ended_assessment(
    user_text: str,
    rubric: dict,
    mode: str,
    last_user_message: str = "",
) -> dict:
    """Deterministic scoring for open-ended answers based on rubric coverage and clarity."""
    text = (user_text or "").strip()
    lower = text.lower()
    concepts = rubric.get("key_concepts", []) or []

    words = _tokenize(text)
    word_count = len(words)
    length_score = 15 if word_count >= 10 else 8 if word_count >= 6 else 2

    matched_concepts, unmatched_concepts = _detect_concept_coverage(text, concepts)
    coverage = len(matched_concepts) / len(concepts) if concepts else 0.0
    base_score = 45 * coverage

    strengths: list[str] = []
    improvements: list[str] = []

    if coverage >= 0.5:
        strengths.append("Response referenced key stage concepts.")
    elif unmatched_concepts:
        improvements.append(f"Include this missing concept: {unmatched_concepts[0]}.")

    if mode == "next_move":
        has_open_question = "?" in text and contains_nonnegated_keyword(
            lower, _OPEN_QUESTION_WORDS
        )
        has_action_signal = contains_nonnegated_keyword(
            lower,
            [
                "ask",
                "explore",
                "clarify",
                "understand",
                "discover",
                "probe",
                "uncover",
                "confirm",
            ],
        )

        context_score = 0
        if last_user_message:
            customer_tokens = {
                token
                for token in _tokenize(last_user_message)
                if len(token) > 3 and token not in _STOPWORDS
            }
            overlap = customer_tokens.intersection(set(words))
            if overlap:
                context_score = 8
                strengths.append("Response connected to the customer's stated context.")
            else:
                improvements.append(
                    "Reference one concrete detail from the customer's last message."
                )

        move_score = 15 if has_open_question else 8 if has_action_signal else 2
        if has_open_question:
            strengths.append("Used an open question to keep discovery moving.")
        else:
            improvements.append("Use one open question to move the conversation forward.")

        score = clamp_score(round(base_score + length_score + move_score + context_score))

        if score >= 75:
            feedback = "Strong next move for this stage."
        elif score >= 45:
            feedback = "Partly aligned, but tighten stage focus."
        else:
            feedback = "This next move is too generic for the current stage."

        return {
            "score": score,
            "feedback": feedback,
            "strengths": _merge_unique_items(strengths, max_items=3),
            "improvements": _merge_unique_items(improvements, max_items=3),
            "key_concepts_got": matched_concepts,
            "key_concepts_missed": unmatched_concepts,
            "coach_tip": _build_coach_tip(unmatched_concepts, mode),
        }

    has_reasoning = contains_nonnegated_keyword(
        lower,
        ["because", "so that", "therefore", "which means", "this helps"],
    )
    has_plan = contains_nonnegated_keyword(
        lower,
        ["first", "next", "then", "after that", "from there"],
    )

    reasoning_score = 12 if has_reasoning else 4
    plan_score = 13 if has_plan else 4

    if has_reasoning:
        strengths.append("Explained why this direction fits.")
    else:
        improvements.append("Explain why this direction fits the stage goal.")

    if has_plan:
        strengths.append("Outlined a clear next-step sequence.")
    else:
        improvements.append("Name a clear order for your next steps.")

    score = clamp_score(round(50 * coverage + length_score + reasoning_score + plan_score))

    if score >= 75:
        feedback = "Strong strategic direction for this stage."
    elif score >= 45:
        feedback = "Direction is partly clear, but needs stronger stage linkage."
    else:
        feedback = "Direction is unclear and misses stage priorities."

    return {
            "score": score,
            "feedback": feedback,
            "strengths": _merge_unique_items(strengths, max_items=3),
            "improvements": _merge_unique_items(improvements, max_items=3),
            "key_concepts_got": matched_concepts,
            "key_concepts_missed": unmatched_concepts,
            "coach_tip": _build_coach_tip(unmatched_concepts, mode),
        }


def _merge_open_ended_result(mode: str, deterministic: dict, llm_result: dict) -> dict:
    """Merge deterministic marks with LLM output for stable but nuanced grading."""
    llm_used = bool(llm_result.get("_used_llm"))
    llm_score = llm_result.get("score", deterministic["score"])

    if llm_used:
        final_score = clamp_score(round(deterministic["score"] * 0.65 + llm_score * 0.35))
    else:
        final_score = deterministic["score"]

    llm_feedback = (llm_result.get("feedback") or "").strip()
    feedback = deterministic["feedback"]
    if llm_used and llm_feedback and llm_feedback.lower() != "unable to evaluate.":
        feedback = f"{feedback} {llm_feedback}"

    merged = {
        "score": final_score,
        "feedback": feedback,
        "strengths": _merge_unique_items(
            deterministic.get("strengths", []), llm_result.get("strengths", [])
        ),
        "improvements": _merge_unique_items(
            deterministic.get("improvements", []), llm_result.get("improvements", [])
        ),
        "key_concepts_got": deterministic.get("key_concepts_got", []),
        "key_concepts_missed": deterministic.get("key_concepts_missed", []),
        "coach_tip": deterministic.get("coach_tip", ""),
    }

    if mode == "next_move":
        merged["alignment"] = (
            llm_result.get("alignment")
            if llm_used and llm_result.get("alignment") in _ENUMS["alignment"]
            else _alignment_from_score(final_score)
        )
    else:
        merged["understanding"] = (
            llm_result.get("understanding")
            if llm_used and llm_result.get("understanding") in _ENUMS["understanding"]
            else _understanding_from_score(final_score)
        )

    return merged


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


def test_quiz_stage_answer(user_answer: str, current_stage: str, flow_type: str) -> dict:
    """Deterministic: did the user correctly ID the current stage and strategy?"""
    expected_stage = current_stage
    expected_strategy = flow_type
    answer_lower = user_answer.strip().lower()

    stage_ok = contains_nonnegated_keyword(answer_lower, expected_stage.lower())
    strategy_ok = contains_nonnegated_keyword(answer_lower, expected_strategy.lower())
    correct = stage_ok and strategy_ok

    # Build feedback based on what user got right
    feedback_map = {
        (True, True): f"Right - {expected_stage.upper()}, {expected_strategy.upper()} strategy.",
        (False, False): f"Close, but not quite - it's {expected_stage.upper()} stage, {expected_strategy.upper()} strategy.",
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


def test_quiz_next_move(
    user_response: str, provider: Any, current_stage: str, flow_type: str, last_user_message: str = ""
) -> dict:
    """Hybrid-scored: deterministic rubric fit blended with LLM judgment."""
    stage, strategy = current_stage, flow_type
    rubric = get_stage_rubric(stage, strategy)
    concepts = ", ".join(rubric.get("key_concepts", []))

    deterministic = _deterministic_open_ended_assessment(
        user_text=user_response,
        rubric=rubric,
        mode="next_move",
        last_user_message=last_user_message,
    )

    prompt = f"""Grade trainee response in {stage} ({strategy}).
Goal: {rubric["goal"]} | Concepts: {concepts}
Customer: "{last_user_message}" | Response: "{user_response}"
JSON: {{"score": <0-100>, "alignment": "strong|partial|weak", "feedback": "<brief>", "strengths": ["..."], "improvements": ["..."]}}"""
    llm_result = _score_with_llm(provider, prompt, {
        "score": 50,
        "alignment": "partial",
        "feedback": "Unable to evaluate.",
        "strengths": [],
        "improvements": [],
    })

    return _merge_open_ended_result("next_move", deterministic, llm_result)


def test_quiz_direction(user_explanation: str, provider: Any, current_stage: str, flow_type: str) -> dict:
    """Hybrid-scored: deterministic strategy clarity blended with LLM judgment."""
    stage, strategy = current_stage, flow_type
    rubric = get_stage_rubric(stage, strategy)
    concepts = ", ".join(rubric.get("key_concepts", []))

    deterministic = _deterministic_open_ended_assessment(
        user_text=user_explanation,
        rubric=rubric,
        mode="direction",
    )

    prompt = f"""Evaluate trainee's understanding in {stage} ({strategy}).
Goal: {rubric["goal"]} | Advance: {rubric["advance_when"]} | Concepts: {concepts}
Trainee: "{user_explanation}"
JSON: {{"score": <0-100>, "understanding": "excellent|good|partial|needs_work", "feedback": "<brief>", "key_concepts_got": ["..."], "key_concepts_missed": ["..."]}}"""
    llm_result = _score_with_llm(provider, prompt, {
        "score": 50,
        "understanding": "partial",
        "feedback": "Unable to evaluate.",
        "key_concepts_got": [],
        "key_concepts_missed": [],
    })

    return _merge_open_ended_result("direction", deterministic, llm_result)


def _score_with_llm(provider: Any, prompt: str, defaults: dict) -> dict:
    """Unified LLM scoring: validates enums, clamps scores, handles fallbacks."""
    try:
        response = provider.chat([{"role": "system", "content": prompt}], temperature=0.3, max_tokens=300)
        parsed = extract_json_from_llm(response.content) if response.content else None
        result = parsed if isinstance(parsed, dict) else {}

        output = {}
        for key, default in defaults.items():
            val = result.get(key, default)
            # Validate enum fields
            if key in _ENUMS:
                if not isinstance(val, str) or val not in _ENUMS[key]:
                    val = default
            # Clamp numeric scores
            if key == "score" and isinstance(val, (int, float)):
                val = clamp_score(int(val))
            output[key] = val

        output["_used_llm"] = isinstance(parsed, dict)
        return output
    except Exception as e:
        logger.warning(f"LLM scoring failed: {e}")
        return {**defaults, "_used_llm": False}
