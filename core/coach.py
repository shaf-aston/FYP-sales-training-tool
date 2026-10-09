"""Training coach: answers trainee questions about the live call."""

import logging

from .constants import COACH_HISTORY_TURNS, LLM
from .quiz import get_stage_rubric

logger = logging.getLogger(__name__)


COACH_STYLES = {
    "tactical": "Tactical and direct, 2-3 sentences: the specific move the trainee should make next.",
    "socratic": "Socratic, 2-3 sentences: one sharp question that exposes the gap the trainee hasn't considered.",
    "teacher": "Teacher, 3-4 sentences: name the technique, why it works, and point to the exchange.",
}


def answer_training_question(router, flow_engine, question, style: str = "tactical"):
    """Answer a trainee's question about the current conversation and sales techniques"""
    stage, flow_type = flow_engine.current_stage, flow_engine.flow_type
    rubric = get_stage_rubric(stage, flow_type)

    history = getattr(flow_engine, "conversation_history", []) or []
    speaker = {"user": "PROSPECT", "assistant": "SELLER"}
    recent = "\n".join(
        f"{speaker.get(message.get('role'), '?')}: {message.get('content', '')}" for message in history[-COACH_HISTORY_TURNS:]
    )

    if style not in COACH_STYLES:
        logger.warning("Unknown coach style %r, defaulting to tactical", style)
        style = "tactical"
    concepts = ", ".join(rubric.get("key_concepts", []))

    system_prompt = (
        f"You're a sales coach. The trainee is practising a {flow_type} sale, now at stage: {stage}.\n"
        f"Goal: {rubric.get('goal', '')} | Advance when: {rubric.get('advance_when', '')} | Concepts: {concepts}\n\n"
        f"Recent:\n{recent}\n\n"
        f"Style: {COACH_STYLES[style]} Plain sentences only: no markdown, lists, headings or bold."
    )

    try:
        response = router.chat_with_fallback(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            **LLM["coach_answer"],
            stage=stage,
        ).response
        answer = (
            response.content.strip()
            if response.content and not response.error
            else "Couldn't get an answer that time - try asking differently."
        )
        return {"answer": answer}
    except Exception as error:
        logger.warning(f"Training Q&A fell back to generic answer: {error}")
        return {"answer": "Sorry, that didn't work. Give it another go."}
