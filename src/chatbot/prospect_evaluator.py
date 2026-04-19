"""Post-session evaluation for prospect mode with 5-criterion scoring."""

from .loader import load_prospect_config
from .utils import clamp_score, extract_json_from_llm, range_label

_GRADETHRESHOLDS = [60, 70, 80, 90]
_GRADE_LABELS = ["F", "D", "C", "B", "A"]


def _grade_from_score(score: int) -> str:
    """Convert numeric score (0-100) to letter grade (F-A)."""
    return range_label(score, _GRADETHRESHOLDS, _GRADE_LABELS)


def evaluate_prospect_session(provider, conversation_history, prospect_state, product_context) -> dict:
    """Evaluate salesperson's prospect-mode session across 5 criteria using LLM."""
    config = load_prospect_config()
    criteria = config.get("evaluation", {}).get("criteria", {})
    
    # Build conversation transcript and metadata
    transcript = "\n".join(
        f"{'SALESPERSON' if m['role'] == 'user' else 'PROSPECT'}: {m['content']}"
        for m in conversation_history
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
    
    try:
        response = provider.chat([{"role": "system", "content": prompt}], temperature=0.3, max_tokens=800)
        result = extract_json_from_llm(response.content)
        if result:
            return _build_evaluation(result, criteria, prospect_state.status)
    except Exception as e:
        pass
    
    return _fallback_evaluation(prospect_state.status)


def _build_evaluation(result: dict, criteria: dict, outcome: str) -> dict:
    """Build structured evaluation from LLM response."""
    criteria_scores = {}
    weighted_total = 0.0
    
    for name, info in criteria.items():
        raw = result.get("criteria_scores", {}).get(name, {})
        score = clamp_score(raw.get("score", 50))
        feedback = raw.get("feedback", "No feedback.")
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
    """Return neutral fallback when LLM evaluation fails."""
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
        "improvements": ["Couldn't finish the evaluation — re-run it when ready."],
        "summary": "The evaluation didn't complete — try again.",
    }
