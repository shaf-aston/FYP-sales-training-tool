"""Post-session evaluation for prospect mode with 5-criterion scoring."""

from .loader import load_prospect_config
from .utils import clamp_score, extract_json_from_llm, range_label

_GRADETHRESHOLDS = [60, 70, 80, 90]
_GRADE_LABELS = ["F", "D", "C", "B", "A"]


def _grade_from_score(score: int) -> str:
    """Convert a numeric score to a letter grade.

    Args:
        score: Numeric score (0-100).

    Returns:
        Letter grade (F, D, C, B, or A).
    """
    return range_label(score, _GRADETHRESHOLDS, _GRADE_LABELS)


def evaluate_prospect_session(
    provider, conversation_history, prospect_state, product_context
) -> dict:
    """Evaluate a salesperson's performance in a prospect-mode session.

    Uses an LLM to score across 5 criteria: needs discovery, rapport building,
    objection handling, solution presentation, and conversation flow.

    Args:
        provider: LLM provider instance.
        conversation_history: List of message dicts with 'role' and 'content'.
        prospect_state: ProspectState instance with session metrics.
        product_context: Product information context string.

    Returns:
        Dictionary with overall_score, grade, criteria_scores, strengths,
        improvements, and summary.
    """
    config = load_prospect_config()
    criteria = config.get("evaluation", {}).get("criteria", {})

    # Build conversation transcript
    transcript = "\n".join(
        f"{'SALESPERSON' if m['role'] == 'user' else 'PROSPECT'}: {m['content']}"
        for m in conversation_history
    )

    outcome = prospect_state.status

    # Build criteria descriptions for prompt
    criteria_text = "\n".join(
        f"- {name}: {info['description']} (weight: {info['weight']})"
        for name, info in criteria.items()
    )

    eval_prompt = f"""You are an expert sales coach evaluating a trainee's performance in a practice session.

CONVERSATION TRANSCRIPT:
{transcript}

SESSION OUTCOME: {outcome}
DIFFICULTY: {prospect_state.difficulty}
PRODUCT CONTEXT: {product_context}
TURNS TAKEN: {prospect_state.turn_count}
PROSPECT'S FINAL READINESS: {prospect_state.readiness:.2f}

EVALUATION CRITERIA:
{criteria_text}

Score each criterion 0-100 and provide specific feedback. Also identify strengths and areas for improvement.

Return your evaluation as JSON:
{{
    "criteria_scores": {{
        "needs_discovery": {{"score": <0-100>, "feedback": "<specific feedback>"}},
        "rapport_building": {{"score": <0-100>, "feedback": "<specific feedback>"}},
        "objection_handling": {{"score": <0-100>, "feedback": "<specific feedback>"}},
        "solution_presentation": {{"score": <0-100>, "feedback": "<specific feedback>"}},
        "conversation_flow": {{"score": <0-100>, "feedback": "<specific feedback>"}}
    }},
    "strengths": ["<strength 1>", "<strength 2>"],
    "improvements": ["<improvement 1>", "<improvement 2>"],
    "summary": "<2-3 sentence overall assessment>"
}}"""

    try:
        messages = [
            {"role": "system", "content": eval_prompt},
            {"role": "user", "content": "Evaluate the salesperson's performance."},
        ]
        response = provider.chat(messages, temperature=0.3, max_tokens=800)

        # Extract JSON
        result = extract_json_from_llm(response.content)
        if result:
            return _build_evaluation(result, criteria, outcome)
    except Exception:
        pass

    # Fallback evaluation
    return _fallback_evaluation(outcome)


def _build_evaluation(result: dict, criteria: dict, outcome: str) -> dict:
    """Build a structured evaluation dict from LLM response.

    Args:
        result: Parsed JSON response from LLM.
        criteria: Configuration dict of evaluation criteria.
        outcome: Session outcome ('sold', 'walked', or 'active').

    Returns:
        Structured evaluation dictionary with overall score and feedback.
    """
    criteria_scores = {}
    weighted_total = 0.0

    for name, info in criteria.items():
        raw = result.get("criteria_scores", {}).get(name, {})
        score = clamp_score(raw.get("score", 50))
        feedback = raw.get("feedback", "No specific feedback available.")
        criteria_scores[name] = {"score": score, "feedback": feedback}
        weighted_total += score * info["weight"]

    overall_score = clamp_score(round(weighted_total))

    return {
        "overall_score": overall_score,
        "grade": _grade_from_score(overall_score),
        "outcome": outcome,
        "criteria_scores": criteria_scores,
        "strengths": result.get("strengths", []),
        "improvements": result.get("improvements", []),
        "summary": result.get("summary", "Evaluation complete."),
    }


def _fallback_evaluation(outcome: str) -> dict:
    """Return a fallback evaluation when LLM evaluation fails.

    Args:
        outcome: Session outcome ('sold', 'walked', or 'active').

    Returns:
        Fallback evaluation dict with neutral scores.
    """
    return {
        "overall_score": 50,
        "grade": "C",
        "outcome": outcome,
        "criteria_scores": {
            "needs_discovery": {
                "score": 50,
                "feedback": "Evaluation unavailable — try running it again.",
            },
            "rapport_building": {
                "score": 50,
                "feedback": "Rapport scoring stopped — give it one more try.",
            },
            "objection_handling": {
                "score": 50,
                "feedback": "Objection handling evaluation failed — run it again?",
            },
            "solution_presentation": {
                "score": 50,
                "feedback": "Solution presentation scoring hiccup — take another shot.",
            },
            "conversation_flow": {
                "score": 50,
                "feedback": "Conversation flow scoring didn't finish — give it another go.",
            },
        },
        "strengths": [],
        "improvements": ["Couldn't finish the evaluation this time around."],
        "summary": "The evaluation didn't complete — re-run it when ready.",
    }
