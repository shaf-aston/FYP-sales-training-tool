"""Training coach module — generates coaching feedback and answers trainee questions.

Extracted from chatbot.py to enforce SRP: chatbot orchestrates, trainer coaches.
"""

import json
import logging
import re

from .quiz import get_stage_rubric
from ..utils import extract_json_from_llm
from ..analytics.session_analytics import SessionAnalytics

logger = logging.getLogger(__name__)


def generate_training(provider, flow_engine, user_msg, bot_reply):
    """Coaching notes for the current exchange. Falls back to rubric text on LLM failure."""
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    rubric = get_stage_rubric(stage, flow_type)

    system_prompt = (
        "Sales coach. JSON only. Ultra-brief. Quote from the exchange. No generics.\n\n"
        f"Stage: {stage} ({flow_type})\n"
        f"Goal: {rubric['goal'][:100]}\n"
        f"Advance when: {rubric['advance_when'][:100]}\n"
        f"USER said: \"{user_msg[:250]}\"\n"
        f"BOT replied: \"{bot_reply[:250]}\"\n\n"
        "Return JSON with EXACTLY this level of specificity:\n"
        "{\n"
        '  "what_happened": "Technique + brief quote, e.g. \'Used future-pacing — asked about life after solving X\'",\n'
        '  "next_move": "Exact signal needed, e.g. \'Disclose a real cost or consequence of staying stuck\'",\n'
        '  "watch_for": ["One concrete pitfall at this stage", "One more if needed"]\n'
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
        # Fallback: provide structured coaching fields derived from the rubric
        return {
            "stage_goal": rubric.get("goal", "—"),
            "what_bot_did": "—",
            "next_trigger": rubric.get("advance_when", "—"),
            "where_heading": rubric.get("goal", ""),
            "watch_for": [],
        }


def answer_training_question(provider, flow_engine, question):
    """Answer a trainee's question about the current conversation and sales techniques."""
    history = flow_engine.conversation_history
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    recent = history[-8:]
    
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in recent
    )

    rubric = get_stage_rubric(stage, flow_type)
    key_concepts = ", ".join(rubric.get("key_concepts", []))
    stage_goal = rubric.get("goal", "")
    advance_when = rubric.get("advance_when", "")

    methodology = "NEPQ (Neuro-Emotional Persuasion Questioning)" if flow_type == "consultative" else "NEEDS → MATCH → CLOSE"

    system_prompt = (
        f"You are an elite cognitive-behavioral sales strategy coach. The trainee is practising {flow_type} sales using {methodology}.\n"
        f"Current stage: {stage} — Goal: {stage_goal}\n"
        f"Advance when: {advance_when}\n"
        f"Key concepts at this stage: {key_concepts}\n\n"
        f"Conversation so far:\n{conversation}\n\n"
        "Your job: answer the trainee's question by applying stark, rigorous psychology-based sales strategy tied to THIS conversation. "
        "Reference exact conversational behaviors. Use cognitive psychology terminology (e.g., 'lexical entrainment', 'vulnerability signaling', 'status framing'). "
        "Explain WHY a technique works psychologically, not just WHAT to do. Never give generic or fluffy advice. Be direct, authoritative, and analytical."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    try:
        llm_response = provider.chat(messages, temperature=0.4, max_tokens=350, stage=stage)
        if llm_response.error or not llm_response.content:
            return {"answer": "Couldn't generate an answer right now. Try rephrasing your question."}
        return {"answer": llm_response.content.strip()}
    except Exception as e:
        logger.warning(f"Training Q&A failed: {e}")
        return {"answer": "Something went wrong generating the answer. Try again."}

def _normalize_stage(raw) -> str:
    """Strip 'Stage.' prefix from stored stage values (e.g. 'Stage.PITCH' → 'pitch')."""
    if isinstance(raw, str) and raw:
        return raw.lower().split('.')[-1]
    return str(raw).lower() if raw else ""


def score_session(session_id: str) -> dict:
    """Score a session based on the F1 Post-session scoring rubric."""
    events = SessionAnalytics.get_session_analytics(session_id)
    
    if not events:
        return {"total_score": 0, "breakdown": {}}
        
    score_breakdown = {
        "stage_progression": 0,
        "signal_detection": 0,
        "objection_handling": 0,
        "questioning_depth": 0,
        "conversation_length": 0
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
            normalized_to_stage = _normalize_stage(event.get("to_stage"))
            if normalized_to_stage:
                stages_reached.add(normalized_to_stage)

            normalized_from_stage = _normalize_stage(event.get("from_stage", ""))
            turns_in_stage = event.get("user_turns_in_stage", None)
            total_transitions += 1

            # Timeouts defined in analysis_config.yaml (fallback to sensible defaults)
            timeouts = {"intent": 6, "logical": 10, "emotional": 10}
            timeout_thresh = timeouts.get(normalized_from_stage, 99)

            # Only count as a signal-driven transition when turns_in_stage is a
            # non-negative integer and strictly less than the timeout threshold.
            if isinstance(turns_in_stage, int) and turns_in_stage >= 0 and turns_in_stage < timeout_thresh:
                signal_transitions += 1
                
        elif event_type == "objection_classified":
            objection_handled = True
            
        elif event_type == "intent_classification":
            if event.get("intent_level") in ["medium", "high"]:
                intent_medium_high_count += 1
                
        elif event_type == "session_end":
            final_stage = _normalize_stage(event.get("final_stage"))
            if final_stage:
                stages_reached.add(final_stage)
            
    # 1. Stage progression (Max 30)
    if "objection" in stages_reached:
        score_breakdown["stage_progression"] = 30
    elif "pitch" in stages_reached:
        score_breakdown["stage_progression"] = 22
    elif "emotional" in stages_reached:
        score_breakdown["stage_progression"] = 15
    elif "logical" in stages_reached:
        score_breakdown["stage_progression"] = 10
    elif "intent" in stages_reached:
        score_breakdown["stage_progression"] = 5
    else:
        score_breakdown["stage_progression"] = 0
        
    # 2. Signal detection (Max 25)
    # If they transitioned, how many were via signal vs timeout?
    if total_transitions > 0:
        ratio = min(1.0, signal_transitions / total_transitions)
        score_breakdown["signal_detection"] = int(25 * ratio)
    else:
        # If no transitions occurred, no signal detected score
        score_breakdown["signal_detection"] = 0
        
    # 3. Objection handling (Max 20)
    score_breakdown["objection_handling"] = 20 if objection_handled else 0
    
    # 4. Questioning depth (Max 15)
    # Give 5 points per medium/high intent found, up to 15
    score_breakdown["questioning_depth"] = min(15, intent_medium_high_count * 5)
    
    # 5. Conversation length (Max 10)
    if 7 <= max_turn <= 12:
        score_breakdown["conversation_length"] = 10
    elif max_turn < 7:
        score_breakdown["conversation_length"] = 5
    elif 12 < max_turn <= 15:
        score_breakdown["conversation_length"] = 8
    else:
        score_breakdown["conversation_length"] = 5
        
    total = min(100, max(0, sum(score_breakdown.values())))
    
    return {
        "total_score": total,
        "breakdown": score_breakdown,
        "metrics": {
            "turns": max_turn,
            "stages_reached": list(stages_reached),
            "signal_ratio": f"{signal_transitions}/{total_transitions}"
        }
    }
