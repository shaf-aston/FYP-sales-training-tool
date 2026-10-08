"""Post-session evaluation for sell mode with 5-criterion scoring."""


from .constants import GRADE_LABELS, GRADE_THRESHOLDS
from .loader import load_sell_config
from .utils import (
    clamp_score,
    range_label,
    tokenize,
)

def _contains_any(text: str, hints: list[str]) -> bool:
    """Return True when any hint phrase appears in the text."""
    lowered = (text or "").lower()
    return any(hint in lowered for hint in hints)


def _weighted_overall(criteria_scores: dict, criteria: dict) -> int:
    """Combine criterion scores into one weighted overall percentage."""
    total = 0.0
    for name, info in criteria.items():
        score = clamp_score(criteria_scores.get(name, {}).get("score", 50))
        total += score * info.get("weight", 0.0)
    return clamp_score(round(total))


def _build_deterministic_criteria_scores(conversation_history: list[dict], criteria: dict) -> dict:
    """Stable deterministic scoring from transcript quality signals."""
    evaluation = load_sell_config()["evaluation"]
    hints, scoring = evaluation["hints"], evaluation["scoring"]
    sales_turns = [message.get("content", "") for message in conversation_history if message.get("role") == "user"]
    buyer_turns = [message.get("content", "") for message in conversation_history if message.get("role") != "user"]

    default_feedback = "Not enough evidence to score this criterion yet."
    if not sales_turns:
        return {
            name: {"score": scoring["empty_score"], "feedback": default_feedback}
            for name in criteria
        }

    sales_count = len(sales_turns)
    buyer_count = len(buyer_turns)
    avg_words = sum(len(tokenize(turn)) for turn in sales_turns) / max(1, sales_count)

    question_turns = sum(1 for turn in sales_turns if "?" in turn)
    open_question_turns = sum(
        1
        for turn in sales_turns
        if "?" in turn and _contains_any(turn, hints["open_question"])
    )
    question_ratio = min(1.0, question_turns / max(1, sales_count))
    open_ratio = open_question_turns / max(1, question_turns)

    rapport_turns = sum(1 for turn in sales_turns if _contains_any(turn, hints["rapport"]))
    rapport_ratio = min(1.0, rapport_turns / max(1, sales_count))

    objection_turns = sum(1 for turn in buyer_turns if _contains_any(turn, hints["objection_cues"]))
    objection_response_turns = sum(
        1 for turn in sales_turns if _contains_any(turn, hints["objection_response"])
    )

    solution_turns = sum(1 for turn in sales_turns if _contains_any(turn, hints["solution"]))
    solution_ratio = min(1.0, solution_turns / max(1, sales_count))

    length_fit = next(
        (band["fit"] for band in scoring["length_fit"]["bands"]
         if band["min_words"] <= avg_words <= band["max_words"]),
        scoring["length_fit"]["other"],
    )
    turn_balance = min(1.0, buyer_count / max(1, sales_count))

    nd, rb, oh, sp, cf = (scoring[key] for key in (
        "needs_discovery", "rapport_building", "objection_handling",
        "solution_presentation", "conversation_flow",
    ))
    computed = {
        "needs_discovery": {
            "score": clamp_score(round(nd["base"] + nd["question_weight"] * question_ratio + nd["open_weight"] * open_ratio)),
            "feedback": (
                "Strong question quality and discovery depth."
                if open_ratio >= nd["good"]
                else "Ask more open discovery questions to uncover needs clearly."
            ),
        },
        "rapport_building": {
            "score": clamp_score(round(rb["base"] + rb["rapport_weight"] * rapport_ratio)),
            "feedback": (
                "Good empathy and trust-building language."
                if rapport_ratio >= rb["good"]
                else "Add brief empathy statements before moving to the next question."
            ),
        },
        "objection_handling": {
            "score": clamp_score(
                round(
                    oh["no_objection_score"]
                    if objection_turns == 0
                    else oh["base"] + oh["response_weight"] * min(1.0, objection_response_turns / max(1, objection_turns))
                )
            ),
            "feedback": (
                "No major objections surfaced; neutral handling score."
                if objection_turns == 0
                else "Acknowledge concerns directly, then reframe toward value and next step."
            ),
        },
        "solution_presentation": {
            "score": clamp_score(round(sp["base"] + sp["solution_weight"] * solution_ratio)),
            "feedback": (
                "Solution language was tied to customer context."
                if solution_ratio >= sp["good"]
                else "Link your recommendation more explicitly to what the prospect said."
            ),
        },
        "conversation_flow": {
            "score": clamp_score(round(cf["base"] + cf["length_weight"] * length_fit + cf["balance_weight"] * turn_balance)),
            "feedback": (
                "Flow was clear and balanced."
                if length_fit >= cf["good_length_fit"] and turn_balance >= cf["good_balance"]
                else "Keep turns concise and balanced so the prospect speaks more."
            ),
        },
    }

    # Preserve config-driven criterion keys (supports custom criteria safely).
    return {
        name: computed.get(
            name,
            {"score": scoring["neutral_score"], "feedback": "Measured with a neutral heuristic baseline."},
        )
        for name in criteria
    }


def _build_deterministic_coaching(criteria_scores: dict) -> tuple[list[str], list[str], str]:
    """Turn criterion scores into strengths, improvements, and one coach tip."""
    labels = {
        "needs_discovery": "needs discovery",
        "rapport_building": "rapport building",
        "objection_handling": "objection handling",
        "solution_presentation": "solution presentation",
        "conversation_flow": "conversation flow",
    }
    tips = {
        "needs_discovery": "Ask one open question that surfaces root cause, not symptoms.",
        "rapport_building": "Start with a brief validation before probing deeper.",
        "objection_handling": "Acknowledge the concern, then reframe with one clear proof point.",
        "solution_presentation": "Tie each benefit directly to a pain point the prospect already shared.",
        "conversation_flow": "Use shorter turns and one question at a time.",
    }

    ranked = sorted(
        criteria_scores.items(), key=lambda item: item[1].get("score", 0), reverse=True
    )
    strong_score = load_sell_config()["evaluation"]["scoring"]["strong_score"]
    strongest = [name for name, score_data in ranked if score_data.get("score", 0) >= strong_score][:2]
    weakest = [name for name, score_data in ranked[-2:]]

    strengths = [f"Strong {labels.get(name, name)}." for name in strongest]
    if not strengths:
        strengths = ["Consistent baseline across criteria."]

    improvements = [tips.get(name, f"Improve {labels.get(name, name)}.") for name in weakest]
    coach_tip = tips.get(weakest[0], "Keep responses focused and tied to the prospect's goal.")

    return strengths, improvements, coach_tip


def _build_deterministic_summary(overall_score: int, outcome: str) -> str:
    """Summarise the session in one short sentence based on score band."""
    decent, solid = load_sell_config()["evaluation"]["scoring"]["summary_bands"]
    if overall_score >= solid:
        return f"Solid session with clear control and progression. Outcome: {outcome}."
    if overall_score >= decent:
        return f"Decent session with room to sharpen execution. Outcome: {outcome}."
    return f"Foundational attempt; focus on core questioning and structure. Outcome: {outcome}."


def _grade_from_score(score: int) -> str:
    """Convert numeric score (0-100) to letter grade (F-A)."""
    return range_label(score, GRADE_THRESHOLDS, GRADE_LABELS)


def evaluate_sell_session(conversation_history, buyer_state) -> dict:
    """Score the salesperson's sell-mode session across 5 criteria, by rules only."""
    config = load_sell_config()
    criteria = config.get("evaluation", {}).get("criteria", {})
    mode_cfg = config.get("sell_mode", {}) if isinstance(config, dict) else {}
    feedback_style = str(mode_cfg.get("feedback_style", "coaching") or "coaching").lower()

    deterministic_scores = _build_deterministic_criteria_scores(conversation_history, criteria)
    deterministic_strengths, deterministic_improvements, deterministic_tip = _build_deterministic_coaching(
        deterministic_scores
    )
    deterministic_overall = _weighted_overall(deterministic_scores, criteria)
    deterministic_pack = {
        "criteria_scores": deterministic_scores,
        "strengths": deterministic_strengths,
        "improvements": deterministic_improvements,
        "summary": _build_deterministic_summary(deterministic_overall, buyer_state.status),
        "coach_tip": deterministic_tip,
    }

    def _apply_style(text: str) -> str:
        """Tighten feedback wording when strict coaching mode is active."""
        if feedback_style in ("strict", "tough", "hard"):
            return text.replace("Try to", "Do").strip()
        return text

    if feedback_style in ("strict", "tough", "hard"):
        deterministic_pack["strengths"] = [
            f"{s}".replace("Strong ", "Good ").strip() for s in deterministic_pack["strengths"]
        ]
        deterministic_pack["improvements"] = [_apply_style(s) for s in deterministic_pack["improvements"]]
        deterministic_pack["coach_tip"] = _apply_style(deterministic_pack.get("coach_tip", ""))

    return _assemble_evaluation(
        buyer_state.status,
        criteria=criteria,
        deterministic=deterministic_pack,
    )


def _assemble_evaluation(
    outcome: str,
    criteria: dict | None = None,
    deterministic: dict | None = None,
) -> dict:
    """Build the final evaluation dict (scores, grade, feedback) from the rules pack."""
    if deterministic and criteria:
        criteria_scores = deterministic.get("criteria_scores", {})
        overall_score = _weighted_overall(criteria_scores, criteria)
        return {
            "overall_score": overall_score,
            "grade": _grade_from_score(overall_score),
            "outcome": outcome,
            "criteria_scores": criteria_scores,
            "strengths": deterministic.get("strengths", []),
            "improvements": deterministic.get("improvements", []),
            "summary": deterministic.get("summary", "Evaluation complete."),
            "coach_tip": deterministic.get("coach_tip", ""),
        }

    defaults = {
        "score": 50,
        "feedback": "Evaluation unavailable.",
    }
    return {
        "overall_score": 50,
        "grade": "C",
        "outcome": outcome,
        "criteria_scores": {
            name: defaults
            for name in ["needs_discovery", "rapport_building", "objection_handling",
                         "solution_presentation", "conversation_flow"]
        },
        "strengths": [],
        "improvements": ["Couldn't finish the evaluation - re-run it when ready."],
        "summary": "The evaluation didn't complete - try again.",
        "coach_tip": "Ask one open question tied to the prospect's main concern.",
    }
