"""Training coach: generates coaching feedback and answers trainee questions"""

import logging

from .providers import create_provider, list_fallback_providers
from .quiz import get_stage_rubric
from .utils import extract_json_from_llm

logger = logging.getLogger(__name__)


# Truncate text to max_words, preserving word boundaries
def _truncate_words(text: str, max_words: int) -> str:
    """Shorten text to a maximum word count without breaking words apart."""
    words = str(text).split()
    return " ".join(words[:max_words]) if len(words) > max_words else text


def _call_training_provider_with_fallbacks(provider, messages, *, temperature, max_tokens, stage):
    """Call the active provider first, then try configured fallbacks if needed."""
    primary = provider.chat(
        messages, temperature=temperature, max_tokens=max_tokens, stage=stage
    )
    if primary and not primary.error and (primary.content or "").strip():
        return primary, getattr(provider, "provider_name", None)

    current_name = getattr(provider, "provider_name", None)
    for next_name in list_fallback_providers(current_name):
        alt = create_provider(next_name)
        if not alt.is_available():
            continue
        response = alt.chat(
            messages, temperature=temperature, max_tokens=max_tokens, stage=stage
        )
        if response.error or not (response.content or "").strip():
            continue
        logger.info(
            "training fallback switched to %s after provider error", next_name
        )
        return response, next_name

    return primary, current_name


def generate_training(provider, flow_engine, user_msg, bot_reply):
    """Coaching notes for the current exchange. Falls back to rubric text on LLM failure"""
    stage = flow_engine.current_stage
    flow_type = flow_engine.flow_type

    rubric = get_stage_rubric(stage, flow_type)

    system_prompt = (
        "You're a sales coach. Reply with JSON only. No markdown, no lists.\n\n"
        f"Stage: {stage} ({flow_type})\n"
        f"Goal: {rubric['goal'][:120]}\n"
        f"Advance when: {rubric['advance_when'][:120]}\n"
        f'USER said: "{user_msg[:200]}"\n'
        f'BOT replied: "{bot_reply[:200]}"\n\n'
        "Return JSON with exactly these fields:\n"
        "{\n"
        '  "what_happened": "Name the specific technique or move the bot just made (15 words max). Be precise - name the pattern, not just the topic.",\n'
        '  "next_move": "One clear, actionable coaching instruction for the next turn (15 words max). Start with a verb.",\n'
        '  "watch_for": ["Specific risk to avoid (8 words max)", "Another specific pitfall (8 words max)"]\n'
        "}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Analyse and provide coaching JSON."},
    ]

    try:
        llm_response, _active_provider_name = _call_training_provider_with_fallbacks(
            provider,
            messages,
            temperature=0.3,
            max_tokens=150,
            stage=stage,
        )
        if llm_response.error or not llm_response.content:
            raise ValueError(
                f"Training provider failed: {getattr(llm_response, 'error', None) or 'empty response'}"
            )

        result = extract_json_from_llm(llm_response.content)
        if not result:
            raise ValueError("Empty or invalid JSON response")

        result["what_happened"] = _truncate_words(result.get("what_happened", ""), 15)
        result["next_move"] = _truncate_words(result.get("next_move", ""), 15)
        result["watch_for"] = [
            _truncate_words(tip, 8) for tip in (result.get("watch_for") or [])
        ]
        return result

    except Exception as error:
        logger.warning(f"Training generation fell back to rubric text: {error}")
        fallback = {
            "what_happened": _truncate_words(rubric.get("goal", "-"), 15),
            "next_move": _truncate_words(rubric.get("advance_when", "-"), 15),
            "watch_for": [],
        }
        return fallback


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


def answer_training_question(provider, flow_engine, question, style: str = "tactical"):
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
        response, _provider_name = _call_training_provider_with_fallbacks(
            provider,
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            temperature=0.4,
            max_tokens=150,
            stage=stage,
        )
        answer = (
            response.content.strip()
            if response.content and not response.error
            else "Couldn't get an answer that time - try asking differently."
        )
        return {"answer": answer}
    except Exception as error:
        logger.warning(f"Training Q&A fell back to generic answer: {error}")
        return {"answer": "Sorry, that didn't work. Give it another go."}
