"""Training coach: generates coaching feedback and answers trainee questions"""

import logging

from .analytics.session_analytics import SessionAnalytics
from .constants import SCORING_RUBRIC, STAGE_TIMEOUTTHRESHOLDS
from .quiz import get_stage_rubric
from .utils import extract_json_from_llm

logger = logging.getLogger(__name__)


def generate_training(provider, flow_engine, user_msg, bot_reply):
    """Coaching notes for the current exchange. Falls back to rubric text on LLM failure"""
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    rubric = get_stage_rubric(stage, flow_type)

    system_prompt = (
        "You're a sales coach. Reply with JSON only. Keep each field to one short sentence — 15 words max. Plain sentences only — no markdown, no lists.\n\n"
        f"Stage: {stage} ({flow_type})\n"
        f"Goal: {rubric['goal'][:100]}\n"
        f"Advance when: {rubric['advance_when'][:100]}\n"
        f'USER said: "{user_msg[:200]}"\n'
        f'BOT replied: "{bot_reply[:200]}"\n\n'
        "Return JSON:\n"
        "{\n"
        '  "what_happened": "e.g. \'Used future-pacing to surface desired outcome\'",\n'
        '  "next_move": "e.g. \'Get them to name a real cost of staying stuck\'",\n'
        '  "watch_for": ["8 words max", "8 words max"]\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Analyse and provide coaching JSON."},
    ]

    try:
        llm_response = provider.chat(messages, temperature=0.3, max_tokens=150, stage=stage)
        if llm_response.error or not llm_response.content:
            raise ValueError("Empty or error response")

        result = extract_json_from_llm(llm_response.content)
        if not result:
            raise ValueError("Empty or invalid JSON response")
        if not isinstance(result.get("watch_for"), list):
            result["watch_for"] = []
        return result

    except Exception as e:
        logger.warning(f"Training generation failed: {e}")
        return {
            "what_happened": rubric.get("goal", "—"),
            "next_move": rubric.get("advance_when", "—"),
            "watch_for": [],
        }


def answer_training_question(provider, flow_engine, question):
    """Answer a trainee's question about the current conversation and sales techniques"""
    history = flow_engine.conversation_history
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    recent = history[-8:]

    conversation = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)

    rubric = get_stage_rubric(stage, flow_type)
    key_concepts = ", ".join(rubric.get("key_concepts", []))
    stage_goal = rubric.get("goal", "")
    advance_when = rubric.get("advance_when", "")

    methodology = (
        "NEPQ (Neuro-Emotional Persuasion Questioning)" if flow_type == "consultative" else "NEEDS → MATCH → CLOSE"
    )

    system_prompt = (
        f"You're an experienced sales coach. The trainee is practising {flow_type} sales using {methodology}.\n"
        f"Current stage: {stage} — Goal: {stage_goal}\n"
        f"Advance when: {advance_when}\n"
        f"Key concepts at this stage: {key_concepts}\n\n"
        f"Conversation so far:\n{conversation}\n\n"
        "Answer the trainee's question with reference to specific moments in the conversation. "
        "Use sales technique names where useful. Explain why a technique works, not just what it is. "
        "Be direct. Specific is better than general."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    try:
        llm_response = provider.chat(messages, temperature=0.4, max_tokens=350, stage=stage)
        if llm_response.error or not llm_response.content:
            return {"answer": "Couldn't get an answer that time — try asking it differently."}
        return {"answer": llm_response.content.strip()}
    except Exception as e:
        logger.warning(f"Training Q&A failed: {e}")
        return {"answer": "Sorry, that didn't work. Give it another go."}


def score_session(session_id: str) -> dict:
    """Score a session based on the F1 Post-session scoring rubric"""
    events = SessionAnalytics.get_session_analytics(session_id)

    if not events:
        return {"total_score": 0, "breakdown": {}}

    def norm(raw):
        if isinstance(raw, str) and raw:
            return raw.lower().split(".")[-1]
        return ""

    score_breakdown = {
        "stage_progression": 0,
        "signal_detection": 0,
        "objection_handling": 0,
        "questioning_depth": 0,
        "conversation_length": 0,
    }

    stages_reached = set()
    total_transitions = 0
    signal_transitions = 0
    objection_handled = False
    intent_medium_high_count = 0
    max_turn = 0

    for event in events:
        event_type = event.get("event_type")
        turn = event.get("user_turn") or event.get("user_turn_count") or 0
        if turn > max_turn:
            max_turn = turn

        if event_type == "stage_transition":
            normalized_to_stage = norm(event.get("to_stage"))
            if normalized_to_stage:
                stages_reached.add(normalized_to_stage)

            normalized_from_stage = norm(event.get("from_stage", ""))
            turns_in_stage = event.get("user_turns_in_stage", None)
            total_transitions += 1

            timeout_thresh = STAGE_TIMEOUTTHRESHOLDS.get(normalized_from_stage, 99)

            if isinstance(turns_in_stage, int) and turns_in_stage >= 0 and turns_in_stage < timeout_thresh:
                signal_transitions += 1

        elif event_type == "objection_classified":
            objection_handled = True

        elif event_type == "intent_classification":
            if event.get("intent_level") in ["medium", "high"]:
                intent_medium_high_count += 1

        elif event_type == "session_end":
            final_stage = norm(event.get("final_stage"))
            if final_stage:
                stages_reached.add(final_stage)

    for stage_name, points in SCORING_RUBRIC["stage_points"].items():
        if stage_name in stages_reached:
            score_breakdown["stage_progression"] = points
            break

    if total_transitions > 0:
        ratio = min(1.0, signal_transitions / total_transitions)
        score_breakdown["signal_detection"] = int(SCORING_RUBRIC["signal_detection_max"] * ratio)
    else:
        score_breakdown["signal_detection"] = 0

    score_breakdown["objection_handling"] = SCORING_RUBRIC["objection_handling_max"] if objection_handled else 0

    score_breakdown["questioning_depth"] = min(
        SCORING_RUBRIC["questioning_depth_max"],
        intent_medium_high_count * SCORING_RUBRIC["questioning_depth_per_hit"],
    )

    sweet_min, sweet_max = SCORING_RUBRIC["sweet_spot_turns"]
    conv_max = SCORING_RUBRIC["conversation_length_max"]
    if sweet_min <= max_turn <= sweet_max:
        score_breakdown["conversation_length"] = conv_max
    elif max_turn < sweet_min:
        score_breakdown["conversation_length"] = conv_max // 2
    elif sweet_max < max_turn <= sweet_max + 3:
        score_breakdown["conversation_length"] = int(conv_max * 0.8)
    else:
        score_breakdown["conversation_length"] = conv_max // 2

    total = min(100, max(0, sum(score_breakdown.values())))

    return {
        "total_score": total,
        "breakdown": score_breakdown,
        "metrics": {
            "turns": max_turn,
            "stages_reached": list(stages_reached),
            "signal_ratio": f"{signal_transitions}/{total_transitions}",
        },
    }
