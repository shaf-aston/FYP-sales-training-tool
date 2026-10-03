"""Training coach: generates coaching feedback and answers trainee questions"""

import logging

from .loader import load_signals, load_yaml
from .quiz import get_stage_rubric
from .utils import contains_nonnegated_keyword

logger = logging.getLogger(__name__)


_NOTES = load_yaml("coach_notes.yaml")
_SIGNALS = load_signals()


def generate_training(flow_engine, user_msg):
    """Coach notes for the current exchange, looked up from coach_notes.yaml (no AI).

    A buyer move in the message (walking, commitment, objection, price question) wins;
    otherwise the note for the current stage is used.
    """
    text = (user_msg or "").lower()
    for move, note in _NOTES["moves"].items():
        if contains_nonnegated_keyword(text, _SIGNALS[move]):
            return dict(note)
    strategy = "transactional" if flow_engine.flow_type == "transactional" else "consultative"
    stage = str(flow_engine.current_stage).split(".")[-1].lower()
    stages = _NOTES["stages"][strategy]
    return dict(stages.get(stage) or stages["intent"])


COACH_STYLES = {
    "tactical": (
        "Style: tactical and direct. Reply in 2-3 plain sentences. "
        "Give the specific move the trainee should make next. "
        "No markdown, no lists, no headings, no bold."
    ),
    "socratic": (
        "Style: Socratic. Reply in 2-3 plain sentences. "
        "Use a sharp question that exposes the gap or surfaces what the trainee hasn't considered. "
        "No markdown, no lists, no headings."
    ),
    "teacher": (
        "Style: teacher. Reply in 3-4 plain sentences. "
        "Name the technique, explain briefly why it works, reference the exchange. "
        "No markdown, no lists, no headings, no bold."
    ),
}


def answer_training_question(router, flow_engine, question, style: str = "tactical"):
    """Answer a trainee's question about the current conversation and sales techniques"""
    stage, flow_type = flow_engine.current_stage, flow_engine.flow_type
    rubric = get_stage_rubric(stage, flow_type)

    history = getattr(flow_engine, "conversation_history", []) or []
    recent = "\n".join(f"{message.get('role', '').upper()}: {message.get('content', '')}" for message in history[-8:])

    methodology = (
        "NEPQ (Neuro-Emotional Persuasion Questioning)"
        if flow_type == "consultative"
        else "NEEDS -> MATCH -> CLOSE"
    )
    if style not in COACH_STYLES:
        logger.warning("Unknown coach style %r, defaulting to tactical", style)
        style = "tactical"
    style_guide = COACH_STYLES[style]
    concepts = ", ".join(rubric.get("key_concepts", []))

    system_prompt = (
        f"You're a sales coach. Trainee is practising {flow_type} using {methodology}.\n"
        f"Stage: {stage} - Goal: {rubric.get('goal', '')}\n"
        f"Advance when: {rubric.get('advance_when', '')} | Concepts: {concepts}\n\n"
        f"Recent: {recent}\n\n{style_guide}"
    )

    try:
        response = router.chat_with_fallback(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            temperature=0.4,
            max_tokens=150,
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
