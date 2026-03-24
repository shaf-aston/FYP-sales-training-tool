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
