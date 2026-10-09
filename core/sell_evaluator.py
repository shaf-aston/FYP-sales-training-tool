"""Post-session evaluation for sell mode: five criteria scored by rule from the transcript."""

from .constants import GRADE_LABELS, GRADE_THRESHOLDS
from .loader import load_buyer_config
from .utils import clamp_score, range_label, tokenize


def _contains_any(text: str, hints: list[str]) -> bool:
    """Return True when any hint phrase appears in the text."""
    lowered = (text or "").lower()
    return any(hint in lowered for hint in hints)


def _weighted_overall(criteria_scores: dict, criteria: dict) -> int:
    """Combine criterion scores into one weighted overall score (0-100)."""
    total = sum(
        clamp_score(criteria_scores[name]["score"]) * info["weight"] for name, info in criteria.items()
    )
    return clamp_score(round(total))


def _criteria_scores(conversation_history: list[dict], evaluation: dict) -> dict:
    """Score every configured criterion from the transcript's language."""
    criteria, hints, scoring = evaluation["criteria"], evaluation["hints"], evaluation["scoring"]
    feedback = evaluation["feedback"]
    sales_turns = [m.get("content", "") for m in conversation_history if m.get("role") == "user"]
    buyer_turns = [m.get("content", "") for m in conversation_history if m.get("role") != "user"]

    if not sales_turns:
        return {
            name: {"score": scoring["empty_score"], "feedback": feedback["no_evidence"]}
            for name in criteria
        }

    sales_count = len(sales_turns)
    buyer_count = len(buyer_turns)
    avg_words = sum(len(tokenize(turn)) for turn in sales_turns) / sales_count

    question_turns = sum(1 for turn in sales_turns if "?" in turn)
    open_question_turns = sum(
        1 for turn in sales_turns if "?" in turn and _contains_any(turn, hints["open_question"])
    )
    question_ratio = min(1.0, question_turns / sales_count)
    open_ratio = open_question_turns / max(1, question_turns)

    rapport_ratio = min(1.0, sum(1 for t in sales_turns if _contains_any(t, hints["rapport"])) / sales_count)
    objection_turns = sum(1 for turn in buyer_turns if _contains_any(turn, hints["objection_cues"]))
    objection_response_turns = sum(1 for t in sales_turns if _contains_any(t, hints["objection_response"]))
    solution_ratio = min(1.0, sum(1 for t in sales_turns if _contains_any(t, hints["solution"])) / sales_count)

    length_fit = next(
        (band["fit"] for band in scoring["length_fit"]["bands"]
         if band["min_words"] <= avg_words <= band["max_words"]),
        scoring["length_fit"]["other"],
    )
    turn_balance = min(1.0, buyer_count / sales_count)

    nd, rb, oh, sp, cf = (scoring[key] for key in (
        "needs_discovery", "rapport_building", "objection_handling",
        "solution_presentation", "conversation_flow",
    ))
    # (score, whether the praise line applies) per criterion.
    computed = {
        "needs_discovery": (
            nd["base"] + nd["question_weight"] * question_ratio + nd["open_weight"] * open_ratio,
            open_ratio >= nd["good"],
        ),
        "rapport_building": (
            rb["base"] + rb["rapport_weight"] * rapport_ratio,
            rapport_ratio >= rb["good"],
        ),
        "objection_handling": (
            oh["no_objection_score"] if objection_turns == 0
            else oh["base"] + oh["response_weight"] * min(1.0, objection_response_turns / objection_turns),
            objection_turns == 0,
        ),
        "solution_presentation": (
            sp["base"] + sp["solution_weight"] * solution_ratio,
            solution_ratio >= sp["good"],
        ),
        "conversation_flow": (
            cf["base"] + cf["length_weight"] * length_fit + cf["balance_weight"] * turn_balance,
            length_fit >= cf["good_length_fit"] and turn_balance >= cf["good_balance"],
        ),
    }

    scores = {}
    for name, info in criteria.items():
        if name not in computed:  # a criterion added in config with no rule of its own
            scores[name] = {"score": scoring["neutral_score"], "feedback": feedback["neutral"]}
            continue
        score, good = computed[name]
        scores[name] = {
            "score": clamp_score(round(score)),
            "feedback": info["praise"] if good else info["advice"],
        }
    return scores


def _coaching(criteria_scores: dict, evaluation: dict) -> tuple[list[str], list[str], str]:
    """Turn criterion scores into strengths, improvements, and one coach tip."""
    criteria, feedback = evaluation["criteria"], evaluation["feedback"]

    def label(name):
        return criteria[name].get("label", name)

    def tip(name):
        return criteria[name].get("tip") or feedback["improve"].format(label=label(name))

    ranked = sorted(criteria_scores.items(), key=lambda item: item[1]["score"], reverse=True)
    strong_score = evaluation["scoring"]["strong_score"]
    strongest = [name for name, data in ranked if data["score"] >= strong_score][:2]
    weakest = [name for name, _ in ranked[-2:]]

    strengths = [feedback["strength"].format(label=label(name)) for name in strongest]
    improvements = [tip(name) for name in weakest]
    return strengths or [feedback["no_strength"]], improvements, improvements[0]


def evaluate_sell_session(conversation_history, buyer_state) -> dict:
    """Score the salesperson's sell-mode session across the configured criteria, by rules only."""
    evaluation = load_buyer_config()["evaluation"]
    criteria_scores = _criteria_scores(conversation_history, evaluation)
    strengths, improvements, coach_tip = _coaching(criteria_scores, evaluation)
    overall_score = _weighted_overall(criteria_scores, evaluation["criteria"])
    summary = range_label(
        overall_score, evaluation["scoring"]["summary_bands"], evaluation["feedback"]["summary"]
    ).format(outcome=buyer_state.status)
    return {
        "overall_score": overall_score,
        "grade": range_label(overall_score, GRADE_THRESHOLDS, GRADE_LABELS),
        "outcome": buyer_state.status,
        "criteria_scores": criteria_scores,
        "strengths": strengths,
        "improvements": improvements,
        "summary": summary,
        "coach_tip": coach_tip,
    }
