"""Post-session evaluation for prospect mode with 5-criterion scoring."""

import re

from .loader import load_prospect_config
from .utils import clamp_score, extract_json_from_llm, range_label

_GRADE_THRESHOLDS = [60, 70, 80, 90]
_GRADE_LABELS = ["F", "D", "C", "B", "A"]

_OPEN_QUESTION_HINTS = ["what", "how", "why", "which", "where", "tell me"]
_RAPPORT_HINTS = [
    "understand",
    "appreciate",
    "makes sense",
    "hear you",
    "fair point",
    "thanks for sharing",
]
_OBJECTION_HINTS = [
    "worried",
    "concern",
    "too expensive",
    "not sure",
    "think about",
    "partner",
    "team",
    "budget",
    "price",
    "cost",
    "skeptic",
    "doubt",
]
_OBJECTION_RESPONSE_HINTS = [
    "understand",
    "fair",
    "makes sense",
    "let's break",
    "option",
    "proof",
    "case",
    "step",
    "plan",
]
_SOLUTION_HINTS = [
    "fit",
    "recommend",
    "option",
    "plan",
    "solution",
    "based on",
    "you said",
    "so you can",
]


def _tokenize(text: str) -> list[str]:
    """Split text into simple lowercase word tokens for rule-based scoring."""
    return re.findall(r"[a-z0-9']+", (text or "").lower())


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


def _merge_unique_items(primary: list[str], secondary: list[str], max_items: int = 3) -> list[str]:
    """Merge two short feedback lists without duplicates or empty entries."""
    seen = set()
    merged = []
    for source in (primary or [], secondary or []):
        for item in source:
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


def _build_deterministic_criteria_scores(conversation_history: list[dict], criteria: dict) -> dict:
    """Stable deterministic scoring from transcript quality signals."""
    sales_turns = [message.get("content", "") for message in conversation_history if message.get("role") == "user"]
    prospect_turns = [message.get("content", "") for message in conversation_history if message.get("role") != "user"]

    default_feedback = "Not enough evidence to score this criterion yet."
    if not sales_turns:
        return {
            name: {"score": 40, "feedback": default_feedback}
            for name in criteria
        }

    sales_count = len(sales_turns)
    prospect_count = len(prospect_turns)
    avg_words = sum(len(_tokenize(turn)) for turn in sales_turns) / max(1, sales_count)

    question_turns = sum(1 for turn in sales_turns if "?" in turn)
    open_question_turns = sum(
        1
        for turn in sales_turns
        if "?" in turn and _contains_any(turn, _OPEN_QUESTION_HINTS)
    )
    question_ratio = min(1.0, question_turns / max(1, sales_count))
    open_ratio = open_question_turns / max(1, question_turns)

    rapport_turns = sum(1 for turn in sales_turns if _contains_any(turn, _RAPPORT_HINTS))
    rapport_ratio = min(1.0, rapport_turns / max(1, sales_count))

    objection_turns = sum(1 for turn in prospect_turns if _contains_any(turn, _OBJECTION_HINTS))
    objection_response_turns = sum(
        1 for turn in sales_turns if _contains_any(turn, _OBJECTION_RESPONSE_HINTS)
    )

    solution_turns = sum(1 for turn in sales_turns if _contains_any(turn, _SOLUTION_HINTS))
    solution_ratio = min(1.0, solution_turns / max(1, sales_count))

    if 8 <= avg_words <= 35:
        length_fit = 1.0
    elif 5 <= avg_words <= 45:
        length_fit = 0.7
    else:
        length_fit = 0.4
    turn_balance = min(1.0, prospect_count / max(1, sales_count))

    computed = {
        "needs_discovery": {
            "score": clamp_score(round(35 + 35 * question_ratio + 30 * open_ratio)),
            "feedback": (
                "Strong question quality and discovery depth."
                if open_ratio >= 0.5
                else "Ask more open discovery questions to uncover needs clearly."
            ),
        },
        "rapport_building": {
            "score": clamp_score(round(45 + 55 * rapport_ratio)),
            "feedback": (
                "Good empathy and trust-building language."
                if rapport_ratio >= 0.4
                else "Add brief empathy statements before moving to the next question."
            ),
        },
        "objection_handling": {
            "score": clamp_score(
                round(
                    60
                    if objection_turns == 0
                    else 35 + 65 * min(1.0, objection_response_turns / max(1, objection_turns))
                )
            ),
            "feedback": (
                "No major objections surfaced; neutral handling score."
                if objection_turns == 0
                else "Acknowledge concerns directly, then reframe toward value and next step."
            ),
        },
        "solution_presentation": {
            "score": clamp_score(round(40 + 60 * solution_ratio)),
            "feedback": (
                "Solution language was tied to customer context."
                if solution_ratio >= 0.35
                else "Link your recommendation more explicitly to what the prospect said."
            ),
        },
        "conversation_flow": {
            "score": clamp_score(round(40 + 35 * length_fit + 25 * turn_balance)),
            "feedback": (
                "Flow was clear and balanced."
                if length_fit >= 0.7 and turn_balance >= 0.6
                else "Keep turns concise and balanced so the prospect speaks more."
            ),
        },
    }

    # Preserve config-driven criterion keys (supports custom criteria safely).
    return {
        name: computed.get(
            name,
            {"score": 60, "feedback": "Measured with a neutral heuristic baseline."},
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
    strongest = [name for name, score_data in ranked if score_data.get("score", 0) >= 70][:2]
    weakest = [name for name, score_data in ranked[-2:]]

    strengths = [f"Strong {labels.get(name, name)}." for name in strongest]
    if not strengths:
        strengths = ["Consistent baseline across criteria."]

    improvements = [tips.get(name, f"Improve {labels.get(name, name)}.") for name in weakest]
    coach_tip = tips.get(weakest[0], "Keep responses focused and tied to the prospect's goal.")

    return strengths, improvements, coach_tip


def _build_deterministic_summary(overall_score: int, outcome: str) -> str:
    """Summarise the session in one short sentence based on score band."""
    if overall_score >= 80:
        return f"Solid session with clear control and progression. Outcome: {outcome}."
    if overall_score >= 65:
        return f"Decent session with room to sharpen execution. Outcome: {outcome}."
    return f"Foundational attempt; focus on core questioning and structure. Outcome: {outcome}."


def _grade_from_score(score: int) -> str:
    """Convert numeric score (0-100) to letter grade (F-A)."""
    return range_label(score, _GRADE_THRESHOLDS, _GRADE_LABELS)


def evaluate_prospect_session(provider, conversation_history, prospect_state, product_context) -> dict:
    """Evaluate salesperson's prospect-mode session across 5 criteria using LLM."""
    config = load_prospect_config()
    criteria = config.get("evaluation", {}).get("criteria", {})
    mode_cfg = config.get("prospect_mode", {}) if isinstance(config, dict) else {}
    scoring_enabled = bool(mode_cfg.get("scoring_enabled", True))
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
        "summary": _build_deterministic_summary(deterministic_overall, prospect_state.status),
        "coach_tip": deterministic_tip,
    }

    def _apply_style(text: str) -> str:
        """Tighten feedback wording when strict coaching mode is active."""
        if feedback_style in ("strict", "tough", "hard"):
            return text.replace("Try to", "Do").replace("Add", "Add").strip()
        return text

    if feedback_style in ("strict", "tough", "hard"):
        deterministic_pack["strengths"] = [
            f"{s}".replace("Strong ", "Good ").strip() for s in deterministic_pack["strengths"]
        ]
        deterministic_pack["improvements"] = [_apply_style(s) for s in deterministic_pack["improvements"]]
        deterministic_pack["coach_tip"] = _apply_style(deterministic_pack.get("coach_tip", ""))

    # Build conversation transcript and metadata
    transcript = "\n".join(
        f"{'SALESPERSON' if message['role'] == 'user' else 'PROSPECT'}: {message['content']}"
        for message in conversation_history
    )
    criteria_text = "\n".join(
        f"- {name}: {info['description']} (weight: {info['weight']})"
        for name, info in criteria.items()
    )

    prompt = f"""You are a sales coach. Evaluate this trainee's performance.

TRANSCRIPT:
{transcript}

OUTCOME: {prospect_state.status} | DIFFICULTY: {prospect_state.difficulty}
TURNS: {prospect_state.turn_count} | PROSPECT READINESS: {prospect_state.readiness:.2f}
PRODUCT CONTEXT: {product_context}

CRITERIA:
{criteria_text}

Return JSON:
{{
    "criteria_scores": {{
        "needs_discovery": {{"score": <0-100>, "feedback": "<feedback>"}},
        "rapport_building": {{"score": <0-100>, "feedback": "<feedback>"}},
        "objection_handling": {{"score": <0-100>, "feedback": "<feedback>"}},
        "solution_presentation": {{"score": <0-100>, "feedback": "<feedback>"}},
        "conversation_flow": {{"score": <0-100>, "feedback": "<feedback>"}}
    }},
    "strengths": ["<str1>", "<str2>"],
    "improvements": ["<imp1>", "<imp2>"],
    "summary": "<2-3 sentence overall assessment>"
}}"""

    if scoring_enabled and provider is not None:
        try:
            response = provider.chat(
                [{"role": "system", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            result = extract_json_from_llm(response.content)
            if result:
                return _build_evaluation(
                    result,
                    criteria,
                    prospect_state.status,
                    deterministic=deterministic_pack,
                )
        except Exception:
            pass

    return _fallback_evaluation(
        prospect_state.status,
        criteria=criteria,
        deterministic=deterministic_pack,
    )


def _build_evaluation(
    result: dict,
    criteria: dict,
    outcome: str,
    deterministic: dict | None = None,
) -> dict:
    """Build structured evaluation from LLM response."""
    criteria_scores = {}
    weighted_total = 0.0

    deterministic_scores = (deterministic or {}).get("criteria_scores", {})

    for name, info in criteria.items():
        raw = result.get("criteria_scores", {}).get(name, {})
        raw = raw if isinstance(raw, dict) else {}

        llm_score = clamp_score(raw.get("score", 50))
        det_score = clamp_score(deterministic_scores.get(name, {}).get("score", llm_score))

        if deterministic:
            score = clamp_score(round(llm_score * 0.7 + det_score * 0.3))
        else:
            score = llm_score

        feedback = raw.get("feedback") or deterministic_scores.get(name, {}).get(
            "feedback", "No feedback."
        )
        criteria_scores[name] = {"score": score, "feedback": feedback}
        weighted_total += score * info["weight"]

    overall_score = clamp_score(round(weighted_total))

    strengths = result.get("strengths", [])
    improvements = result.get("improvements", [])
    summary = result.get("summary", "")
    coach_tip = ""

    if deterministic:
        strengths = _merge_unique_items(strengths, deterministic.get("strengths", []))
        improvements = _merge_unique_items(
            improvements, deterministic.get("improvements", [])
        )
        summary = summary or deterministic.get("summary", "Evaluation complete.")
        coach_tip = deterministic.get("coach_tip", "")

    return {
        "overall_score": overall_score,
        "grade": _grade_from_score(overall_score),
        "outcome": outcome,
        "criteria_scores": criteria_scores,
        "strengths": strengths,
        "improvements": improvements,
        "summary": summary or "Evaluation complete.",
        "coach_tip": coach_tip,
    }


def _fallback_evaluation(
    outcome: str,
    criteria: dict | None = None,
    deterministic: dict | None = None,
) -> dict:
    """Return neutral fallback when LLM evaluation fails."""
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
