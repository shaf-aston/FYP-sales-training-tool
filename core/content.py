"""LAYER 2: Prompt rules - builds the system prompt for the AI-written seller.

The prompt is rebuilt every turn: base facts and rules, then this turn's
acknowledgement and tactic, the stage prompt, and any objection or override block.
Layer 3 (response_guardrails) checks the reply afterwards.
"""

import random
from typing import Any

from .loader import (
    load_signals,
    get_adaptation_template,
)
from .prompts import (
    get_prompt,
    generate_init_greeting,
    get_base_prompt,
    get_ack_guidance,
    get_override_guidance,
)
from .analysis import (
    analyse_state,
    extract_preferences,
    detect_ack_context,
    extract_user_keywords,
    detect_topic_drift,
    is_literal_question,
)
from .constants import TERSE_INPUT_THRESHOLD
from .enums import Stage, Strategy

from .objection import build_objection_context

ELICITATION_TACTICS = [
    "Most people in your situation feel trapped between their current setup and exploring new options. What's kept you from making a move so far?",
    "You've probably tried handling this yourself already. What's made that approach work for you up until now?",
    "I'm guessing this isn't urgent, but there's something nudging you to look at alternatives. What is it?",
]


def _build_tactic_guidance(strategy: str, state: Any, user_message: str, stage: str) -> str:
    """Return an adaptation block when user state calls for a tactical shift.

    Returns an empty string when the user is already engaged and no adaptation
    is needed.
    """
    if state.decisive:
        return get_adaptation_template("decisive_user", strategy=strategy, stage=stage)

    if state.intent == "low" or state.guarded or state.question_fatigue:
        if is_literal_question(user_message):
            return get_adaptation_template("literal_question")

        if state.intent == "low":
            reason = "low intent"
        elif state.guarded:
            reason = "guarded response"
        else:
            reason = "question fatigue (2+ recent questions)"

        elicitation_example = ""
        if strategy == Strategy.CONSULTATIVE:
            elicitation_example = random.choice(ELICITATION_TACTICS)

        return get_adaptation_template(
            "low_intent_guarded",
            strategy=strategy,
            stage=stage,
            reason=reason,
            elicitation_example=elicitation_example,
        )

    return ""


# Exported signals for consumers (e.g. flow.py)
SIGNALS = load_signals()

# Export public symbols
__all__ = [
    "generate_stage_prompt",
    "generate_init_greeting",
    "get_prompt",
    "SIGNALS",
]


def _get_preference_and_keyword_context(history, preferences):
    """Extract user preferences and keywords, then inject into prompt context.

    Embedding user's own words (keywords) into responses increases lexical entrainment,
    which improves rapport. Preferences guide personalization. Both blocks are formatted
    as explicit instructions so the LLM treats them as part of the system prompt, not data.
    """
    preference_context = (
        f"\nUSER PREFERENCES: {preferences}\nUSE these to personalize your response."
        if preferences
        else ""
    )
    user_keywords = extract_user_keywords(history)
    keyword_context = ""
    if user_keywords:
        keyword_context = f"""
USER'S OWN WORDS:
Terms the user has used: {", ".join(user_keywords)}
Naturally embed 1-2 into a new thought in your response.
"""

    return preference_context + keyword_context


def _get_recent_assistant_question(history) -> str:
    """Return the most recent assistant question, if any."""
    if not history:
        return ""
    for msg in reversed(history):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "").strip()
        if "?" in content:
            return content
    return ""


def _get_stage_specific_prompt(
    strategy, stage, state, user_message, history, objection_data=None
):
    """Return (stage_prompt, stage_context); context is the objection SOP, empty outside OBJECTION."""
    prompt_key = "intent_low" if stage == Stage.INTENT and state.intent == "low" else stage
    stage_context = build_objection_context(
        strategy=strategy,
        stage=stage,
        user_message=user_message,
        history=history,
        objection_data=objection_data,
    )
    return get_prompt(strategy, prompt_key), stage_context


def generate_stage_prompt(
    strategy: str,
    stage: str,
    product_context: str,
    history: list[dict[str, str]],
    user_message: str = "",
    objection_data: dict | None = None,
    turn_state=None,
) -> str:
    """Build the full system prompt for this turn.

    Order: facts and rules first, the stage instruction in the middle, and
    turn-specific nudges (drift, repetition, terse) last, nearest the reply.
    History is sent as chat messages, not copied in here.
    """
    base = get_base_prompt(product_context, strategy)
    state = (
        turn_state
        if turn_state is not None
        else analyse_state(history, user_message, signal_keywords=SIGNALS)
    )
    preferences = extract_preferences(history)

    override = get_override_guidance(user_message, stage, history, preferences)

    # ack level - must appear before the stage prompt
    ack_guidance = get_ack_guidance(detect_ack_context(user_message, history, state))

    # tactic guidance (adaptation for low-intent / guarded / decisive users)
    tactic_guidance = _build_tactic_guidance(strategy, state, user_message, stage)

    # stage-specific prompt and optional context block (e.g. objection SOP)
    stage_prompt, stage_context = _get_stage_specific_prompt(
        strategy, stage, state, user_message, history, objection_data
    )

    # assemble final prompt blocks
    drift_note = detect_topic_drift(user_message, stage)
    preference_keyword_context = _get_preference_and_keyword_context(
        history, preferences
    )
    recent_assistant_question = _get_recent_assistant_question(history)
    repetition_guard = ""
    if stage == Stage.INTENT and recent_assistant_question:
        repetition_guard = (
            f"\nYOU LAST ASKED: {recent_assistant_question}\n"
            "Ask something new.\n"
        )

    terse_guidance = ""
    msg_len = len(user_message.split()) if user_message else 0
    if msg_len < TERSE_INPUT_THRESHOLD and stage not in (Stage.INTENT, Stage.OUTCOME):
        terse_guidance = "\nSHORT ANSWER: don't over-probe.\n"

    return (
        base
        + "\n"
        + ack_guidance
        + tactic_guidance
        + stage_prompt
        + stage_context
        + override
        + drift_note
        + repetition_guard
        + preference_keyword_context
        + terse_guidance
    )
