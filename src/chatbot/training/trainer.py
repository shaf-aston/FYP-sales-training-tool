"""Training coach module — generates coaching feedback and answers trainee questions.

Extracted from chatbot.py to enforce SRP: chatbot orchestrates, trainer coaches.
"""

import json
import logging
import re

from .quiz import get_stage_rubric

logger = logging.getLogger(__name__)


def generate_training(provider, flow_engine, user_msg, bot_reply):
    """Generate coaching notes for the current exchange via lightweight LLM call.
    
    Args:
        provider: LLM provider instance with chat() method
        flow_engine: SalesFlowEngine instance (for stage, flow_type, turn count)
        user_msg: User's message
        bot_reply: Bot's reply
        
    Returns:
        dict: Coaching feedback with stage_goal, what_bot_did, next_trigger, where_heading, watch_for
    """
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    rubric = get_stage_rubric(stage, flow_type)

    history = flow_engine.conversation_history
    recent = history[-6:]

    context = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in recent
    ) if recent else "No prior context"

    rubric_context = (
        f"Stage Goal: {rubric['goal']}\n"
        f"Advance When: {rubric['advance_when']}\n"
        f"Key Concepts: {', '.join(rubric.get('key_concepts', []))}"
    )

    system_prompt = (
        f"You're a sales coach analyzing this exchange. Reply with JSON only:\n\n"
        f"CONTEXT: {flow_type} sales | Stage: {stage}\n"
        f"{rubric_context}\n\n"
        f"Recent conversation:\n{context}\n\n"
        f"Current:\nUSER: {user_msg}\nBOT: {bot_reply}\n\n"
        "Return JSON:\n"
        "{\n"
        '  "stage_goal": "What this stage aims to achieve",\n'
        '  "what_bot_did": "Technique used here",\n'
        '  "next_trigger": "What signal advances to next stage",\n'
        '  "where_heading": "Next conversational move",\n'
        '  "watch_for": ["Warning 1", "Warning 2"]\n'
        "}"
    )

    if flow_type == "consultative" and stage not in ["pitch", "objection"]:
        system_prompt += "\nNOTE: Don't recommend pricing talk unless prospect asks or stage is 'pitch'."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Analyse and provide coaching JSON."},
    ]

    try:
        llm_response = provider.chat(messages, temperature=0.3, max_tokens=350, stage=stage)
        if llm_response.error or not llm_response.content:
            raise ValueError("Empty or error response")

        raw = llm_response.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        if not isinstance(result.get("watch_for"), list):
            result["watch_for"] = []
        return result

    except Exception as e:
        logger.warning(f"Training generation failed: {e}")
        return {
            "stage_goal": rubric["goal"],
            "what_bot_did": "—",
            "next_trigger": rubric["advance_when"],
            "where_heading": "—",
            "watch_for": [],
        }


def answer_training_question(provider, flow_engine, question):
    """Answer a trainee's question about the current conversation and sales techniques.
    
    Args:
        provider: LLM provider instance with chat() method
        flow_engine: SalesFlowEngine instance (for history, stage, flow_type)
        question: Trainee's question string
        
    Returns:
        dict: {"answer": str} with detailed, specific coaching response
    """
    history = flow_engine.conversation_history
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    recent = history[-8:]
    
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content']}"
        for m in recent
    )

    system_prompt = (
        f"You're a sales coach answering a trainee's question during roleplay.\n"
        f"Strategy: {flow_type} | Stage: {stage}\n\n"
        f"Recent conversation:\n{conversation}\n\n"
        "Answer specifically about THIS conversation, not generic advice. "
        "Be direct and concrete. 2-3 sentences."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    try:
        llm_response = provider.chat(messages, temperature=0.5, max_tokens=250, stage=stage)
        if llm_response.error or not llm_response.content:
            return {"answer": "Couldn't generate an answer right now. Try rephrasing your question."}
        return {"answer": llm_response.content.strip()}
    except Exception as e:
        logger.warning(f"Training Q&A failed: {e}")
        return {"answer": "Something went wrong generating the answer. Try again."}

def score_session(session_id: str) -> dict:
    """Score a session based on the F1 Post-session scoring rubric."""
    from ..analytics.session_analytics import SessionAnalytics
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
            # Normalize stage tokens: analytics may store values like 'Stage.PITCH'
            raw_to_stage = event.get("to_stage")
            if isinstance(raw_to_stage, str) and raw_to_stage:
                normalized_to_stage = raw_to_stage.lower().split('.')[-1]
            else:
                normalized_to_stage = str(raw_to_stage).lower() if raw_to_stage else ""

            if normalized_to_stage:
                stages_reached.add(normalized_to_stage)

            # Check if transition was on signal or timeout (guard invalid values)
            raw_from_stage = event.get("from_stage", "")
            if isinstance(raw_from_stage, str) and raw_from_stage:
                normalized_from_stage = raw_from_stage.lower().split('.')[-1]
            else:
                normalized_from_stage = str(raw_from_stage).lower() if raw_from_stage else ""

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
            final_stage_raw = event.get("final_stage")
            if isinstance(final_stage_raw, str) and final_stage_raw:
                final_stage = final_stage_raw.lower().split('.')[-1]
            else:
                final_stage = str(final_stage_raw).lower() if final_stage_raw else ""

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
        ratio = signal_transitions / total_transitions
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
        
    total = sum(score_breakdown.values())
    
    return {
        "total_score": total,
        "breakdown": score_breakdown,
        "metrics": {
            "turns": max_turn,
            "stages_reached": list(stages_reached),
            "signal_ratio": f"{signal_transitions}/{total_transitions}"
        }
    }
