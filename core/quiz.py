"""Quiz assessment: stage ID (by rule), next move and direction (rules score, the AI may add wording)."""

import logging
import random
from typing import Any

from .constants import LLM
from .loader import load_yaml
from .services.provider_router import complete_json
from .selling_quality import NEGATIVE_SIGNALS, REASONS, score_seller_turn
from .utils import (
    clamp_score,
    contains_nonnegated_keyword,
    merge_unique_items,
    range_label,
    tokenize,
)

logger = logging.getLogger(__name__)

# The labels an AI answer may use; the prompts in quiz.yaml list the same ones.
_ENUMS = {
    "alignment": {"strong", "partial", "weak"},
    "understanding": {"excellent", "good", "partial", "needs_work"},
}


def load_quiz_config() -> dict:
    return load_yaml("quiz.yaml")


def _content_words(text: str, stopwords) -> list[str]:
    return [token for token in tokenize(text) if len(token) > 3 and token not in stopwords]


def _concept_coverage(answer: str, concepts: list[str], stopwords) -> tuple[list[str], list[str]]:
    """(concepts named, concepts missed), by any content word of the concept appearing in the answer."""
    answer_tokens = set(tokenize(answer))
    named, missed = [], []
    for concept in concepts:
        if any(token in answer_tokens for token in _content_words(concept, stopwords)):
            named.append(concept)
        else:
            missed.append(concept)
    return named, missed


def _open_ended_assessment(user_text: str, rubric: dict, mode: str, last_user_message: str = "") -> dict:
    """Rule-based score for a next-move or direction answer: rubric coverage and clarity."""
    config = load_quiz_config()
    points, words, feedback = config["scoring"], config["words"], config["feedback"]
    stopwords = set(words["stopwords"])
    text = (user_text or "").strip()
    lower = text.lower()
    concepts = rubric["key_concepts"]

    answer_words = tokenize(text)
    length = points["length_points"]
    length_score = (
        length["full"] if len(answer_words) >= length["full_words"]
        else length["part"] if len(answer_words) >= length["part_words"]
        else length["short"]
    )

    named, missed = _concept_coverage(text, concepts, stopwords)
    coverage = len(named) / len(concepts) if concepts else 0.0

    strengths: list[str] = []
    improvements: list[str] = []
    if coverage >= points["coverage_good"]:
        strengths.append(feedback["concepts_named"])
    elif missed:
        improvements.append(feedback["concept_missing"].format(concept=missed[0]))

    mode_text = feedback[mode]
    if mode == "next_move":
        move = points["next_move_points"]
        has_open_question = "?" in text and contains_nonnegated_keyword(lower, words["open_question"])
        has_action = contains_nonnegated_keyword(lower, words["action"])

        context_score = 0
        if last_user_message:
            if set(_content_words(last_user_message, stopwords)) & set(answer_words):
                context_score = move["context"]
                strengths.append(mode_text["context_used"])
            else:
                improvements.append(mode_text["context_missing"])

        if has_open_question:
            strengths.append(mode_text["open_question"])
        else:
            improvements.append(mode_text["no_open_question"])
        move_score = (
            move["open_question"] if has_open_question
            else move["action"] if has_action
            else move["neither"]
        )
        score = points["coverage_points"]["next_move"] * coverage + length_score + move_score + context_score
    else:
        direction = points["direction_points"]
        has_reasoning = contains_nonnegated_keyword(lower, words["reasoning"])
        has_plan = contains_nonnegated_keyword(lower, words["plan"])
        strengths += [mode_text["reasoning"]] if has_reasoning else []
        improvements += [] if has_reasoning else [mode_text["no_reasoning"]]
        strengths += [mode_text["plan"]] if has_plan else []
        improvements += [] if has_plan else [mode_text["no_plan"]]
        score = (
            points["coverage_points"]["direction"] * coverage
            + length_score
            + (direction["reasoning"] if has_reasoning else direction["missing"])
            + (direction["plan"] if has_plan else direction["missing"])
        )

    score = clamp_score(round(score))
    return {
        "score": score,
        "feedback": range_label(score, points["alignment_bands"], mode_text["bands"]),
        "strengths": merge_unique_items(strengths, max_items=3),
        "improvements": merge_unique_items(improvements, max_items=3),
        "key_concepts_got": named,
        "key_concepts_missed": missed,
        "coach_tip": (
            feedback["coach_tip_concept"].format(concept=missed[0]) if missed else mode_text["coach_tip"]
        ),
    }


def _merge_open_ended_result(mode: str, rules: dict, llm_result: dict) -> dict:
    """Rules set the score; the LLM may only add wording (feedback, strengths, improvements)."""
    config = load_quiz_config()
    llm_used = bool(llm_result.get("_used_llm"))
    score = rules["score"]

    llm_feedback = (llm_result.get("feedback") or "").strip()
    feedback = rules["feedback"]
    if llm_used and llm_feedback and llm_feedback.lower() != config["feedback"]["ai_unavailable"].lower():
        feedback = f"{feedback} {llm_feedback}"

    merged = {
        "score": score,
        "feedback": feedback,
        "strengths": merge_unique_items(rules["strengths"], llm_result.get("strengths", []), max_items=4),
        "improvements": merge_unique_items(rules["improvements"], llm_result.get("improvements", []), max_items=4),
        "key_concepts_got": rules["key_concepts_got"],
        "key_concepts_missed": rules["key_concepts_missed"],
        "coach_tip": rules["coach_tip"],
    }

    bands = config["scoring"]
    if mode == "next_move":
        merged["alignment"] = (
            llm_result["alignment"]
            if llm_used and llm_result.get("alignment") in _ENUMS["alignment"]
            else range_label(score, bands["alignment_bands"], ["weak", "partial", "strong"])
        )
    else:
        merged["understanding"] = (
            llm_result["understanding"]
            if llm_used and llm_result.get("understanding") in _ENUMS["understanding"]
            else range_label(score, bands["understanding_bands"], ["needs_work", "partial", "good", "excellent"])
        )
    return merged


def get_stage_rubric(stage: str, strategy: str) -> dict:
    """Rubric for a stage: goal, advance_when, key_concepts. A stage with no rubric is a config error."""
    return load_quiz_config()["stages"][str(strategy)][str(stage)]


def get_quiz_question(quiz_type: str) -> str:
    """A random question for the quiz type ("stage", "next-move", "direction")."""
    questions = load_quiz_config()["questions"]
    normalized_type = quiz_type.replace("-", "_").lower()
    return random.choice(questions.get(normalized_type) or questions["default"])


def _friendly(kind: str, value: Any) -> str:
    """Plain-English name for a stage or strategy id."""
    key = str(value)
    return load_quiz_config()[kind].get(key, key)


def score_stage_answer(user_answer: str, current_stage: str, strategy: str) -> dict:
    """Did the learner name the current stage and strategy? By rule, no AI.

    The answer may use either the id ("logical") or the plain name ("Understanding
    the problem"). Feedback only ever shows the plain name.
    """
    stage_name = _friendly("stage_names", current_stage)
    strategy_name = _friendly("strategy_names", strategy)
    answer_lower = user_answer.strip().lower()

    stage_ok = contains_nonnegated_keyword(answer_lower, [str(current_stage), stage_name.lower()])
    strategy_ok = contains_nonnegated_keyword(answer_lower, [str(strategy), strategy_name.lower()])
    correct = stage_ok and strategy_ok

    templates = load_quiz_config()["feedback"]["stage"]
    template = {
        (True, True): templates["both_right"],
        (False, False): templates["both_wrong"],
        (False, True): templates["strategy_only"],
        (True, False): templates["stage_only"],
    }[(stage_ok, strategy_ok)]

    if correct:
        score = 1
    elif stage_ok or strategy_ok:
        score = load_quiz_config()["scoring"]["stage_partial_credit"]
    else:
        score = 0

    return {
        "correct": correct,
        "score": score,
        "user_answer": user_answer,
        "expected": {"stage": stage_name, "strategy": strategy_name},
        "feedback": template.format(stage=stage_name, strategy=strategy_name),
    }


def build_sell_question(turns: list[dict]) -> dict | None:
    """Ask about the seller's own weakest turn (earliest on a tie), or None if none yet."""
    if not turns:
        return None
    turn = min(turns, key=lambda t: (t["rating"], t["turn"]))
    template = load_quiz_config()["sell_question"]
    return {
        "turn": turn["turn"],
        "question": template.format(turn=turn["turn"], line=turn["seller"]),
    }


def score_sell_answer(answer: str, turn: dict) -> dict:
    """Rate the seller's replacement line with the same judge that rated the original."""
    new = score_seller_turn(
        answer, buyer_message=turn["buyer_before"], completed_turns=turn["turn"] - 1
    )
    old = turn["rating"]
    templates = load_quiz_config()["sell_feedback"]
    key = "better" if new.rating > old else "same" if new.rating == old else "worse"
    pairs = list(zip(new.signals, new.reasons))
    # The original turn's evidence, worded exactly as the turn review words it.
    before = [
        {"text": REASONS[sig], "good": sig not in NEGATIVE_SIGNALS}
        for sig in turn.get("signals", [])
        if sig in REASONS
    ]
    return {
        "score": round((new.rating - 1) / 4 * 100),
        "feedback": templates[key].format(old=old, new=new.rating),
        "strengths": [r for sig, r in pairs if sig not in NEGATIVE_SIGNALS],
        "improvements": [r for sig, r in pairs if sig in NEGATIVE_SIGNALS],
        "before": before,
    }


def _prompt(kind: str, rubric: dict, stage: str, strategy: str, answer: str, customer: str = "") -> str:
    return load_quiz_config()["prompts"][kind].format(
        stage=_friendly("stage_names", stage),
        strategy=_friendly("strategy_names", strategy),
        goal=rubric["goal"],
        advance_when=rubric["advance_when"],
        concepts=", ".join(rubric["key_concepts"]),
        customer=customer,
        answer=answer,
    )


def score_next_move(
    user_response: str, router: Any, current_stage: str, strategy: str, last_user_message: str = ""
) -> dict:
    """Rules score how well the suggested next move fits the stage; the AI may add wording."""
    rubric = get_stage_rubric(current_stage, strategy)
    rules = _open_ended_assessment(user_response, rubric, "next_move", last_user_message)
    prompt = _prompt("next_move", rubric, current_stage, strategy, user_response, last_user_message)
    llm_result = _score_with_llm(router, prompt, {
        "score": load_quiz_config()["scoring"]["llm_fallback_score"],
        "alignment": "partial",
        "feedback": load_quiz_config()["feedback"]["ai_unavailable"],
        "strengths": [],
        "improvements": [],
    })
    return _merge_open_ended_result("next_move", rules, llm_result)


def score_direction(user_explanation: str, router: Any, current_stage: str, strategy: str) -> dict:
    """Rules score how clear the learner's strategy is; the AI may add wording."""
    rubric = get_stage_rubric(current_stage, strategy)
    rules = _open_ended_assessment(user_explanation, rubric, "direction")
    prompt = _prompt("direction", rubric, current_stage, strategy, user_explanation)
    llm_result = _score_with_llm(router, prompt, {
        "score": load_quiz_config()["scoring"]["llm_fallback_score"],
        "understanding": "partial",
        "feedback": load_quiz_config()["feedback"]["ai_unavailable"],
        "key_concepts_got": [],
        "key_concepts_missed": [],
    })
    return _merge_open_ended_result("direction", rules, llm_result)


def _score_with_llm(router: Any, prompt: str, defaults: dict) -> dict:
    """The AI's JSON answer, keeping only known labels and a clamped score; `defaults` on any failure."""
    try:
        parsed = complete_json(router, [{"role": "system", "content": prompt}], **LLM["quiz"])
        result = parsed or {}

        output = {}
        for key, default in defaults.items():
            val = result.get(key, default)
            if key in _ENUMS and (not isinstance(val, str) or val not in _ENUMS[key]):
                val = default
            if key == "score" and isinstance(val, (int, float)):
                val = clamp_score(int(val))
            output[key] = val

        output["_used_llm"] = parsed is not None
        return output
    except Exception as e:
        logger.warning(f"LLM scoring failed: {e}")
        return {**defaults, "_used_llm": False}
