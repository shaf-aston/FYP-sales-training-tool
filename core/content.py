"""LAYER 2: Prompt Rules - Constrains LLM generation via system prompt rules.

Assembles stage-specific rules that are embedded in the system prompt before the LLM
sees the user message. Rules guide the LLM to self-constrain during generation:
- "No closing questions in INTENT stage"
- "Do not mention price until PITCH stage"
- "Ask one question per turn maximum"
- Strategy-specific rules (e.g., consultative/transactional prompts)

Uses signal detections from analysis.py to select which rules apply.
Execution order: 3rd (after signal detection and FSM advancement check in chatbot.chat()).
Conceptually: Middle defensive layer (constrains bad generation before it happens).
See three_layer_architecture.puml for full defense-in-depth diagram.
"""

import random
from typing import Any

from .loader import (
    load_signals,
    load_objection_flows,
    get_adaptation_template,
)
from .prompts import (
    get_prompt,
    generate_init_greeting,
    get_base_prompt,
    get_ack_guidance,
    check_override_condition,
    format_conversation_context,
)
from .analysis import (
    analyse_state,
    extract_preferences,
    detect_ack_context,
    extract_user_keywords,
    detect_topic_drift,
    is_literal_question,
)
from .constants import PERSONA_CHECKPOINT_TURNS, TERSE_INPUT_THRESHOLD
from .utils import Stage, Strategy

from .objection import _build_objection_context

ELICITATION_TACTICS = [
    "Most people in your situation feel trapped between their current setup and exploring new options. What's kept you from making a move so far?",
    "You've probably tried handling this yourself already. What's made that approach work for you up until now?",
    "I'm guessing this isn't urgent, but there's something nudging you to look at alternatives. What is it?",
]


def _build_tactic_guidance(strategy: str, state: Any, user_message: str) -> str:
    """Return an adaptation block when user state calls for a tactical shift.

    Returns an empty string when the user is already engaged and no adaptation
    is needed.
    """
    if state.decisive:
        return get_adaptation_template("decisive_user", strategy=strategy)

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
            reason=reason,
            elicitation_example=elicitation_example,
        )

    return ""


# Exported signals for consumers (e.g. flow.py)
SIGNALS = load_signals()
# Backwards-compatible alias used by older tests and modules
_OBJECTION_FLOWS_RAW = load_objection_flows()
# expose only the `sop_flows` section for backward compatibility with tests
SOP_FLOWS = _OBJECTION_FLOWS_RAW.get("sop_flows", {})

# Export public symbols
__all__ = [
    "generate_stage_prompt",
    "generate_init_greeting",
    "get_prompt",
    "SIGNALS",
    "SOP_FLOWS",
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
USER'S OWN WORDS (embed keywords, don't replay sentences):
Terms the user has used: {", ".join(user_keywords)}
Naturally embed 1-2 into your response. Do NOT replay full sentences.
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
    """Select the stage prompt and, for objections, build the separate context block.

    Returns:
        tuple[str, str]: (stage_prompt, stage_context)
            stage_prompt: The instruction template for the active stage.
            stage_context: Extra objection SOP text, or an empty string for non-objection stages.
    """

    if stage == Stage.INTENT:
        prompt_key = "intent_low" if state.intent == "low" else "intent"
        return get_prompt(strategy, prompt_key), ""

    if stage in (Stage.LOGICAL, Stage.EMOTIONAL):
        return get_prompt(strategy, stage), ""

    if stage == Stage.OBJECTION:
        objection_context = _build_objection_context(
            strategy=strategy,
            stage=stage,
            user_message=user_message,
            history=history,
            objection_data=objection_data,
        )
        return get_prompt(strategy, stage), objection_context

    return get_prompt(strategy, stage), ""


def generate_stage_prompt(
    strategy: str,
    stage: str,
    product_context: str,
    history: list[dict[str, str]],
    user_message: str = "",
    objection_data: dict | None = None,
    turn_state=None,
    include_history: bool = True,
) -> str:
    """Build the full system prompt for this turn.

    Assembly order and rationale:
        1. base+rules - anchor factual constraints first for primacy
        2. ack - keep acknowledgement guidance before stage instructions
        3. tactics - adaptation context should shape how the stage runs
        4. stage_prompt - the main instruction for the active stage
        5. stage_context - objection SOP details directly below the stage prompt
        6. drift_note - correction if the user drifted away from the stage goal
        7. history - late for recency bias
        8. preferences - user's own language near generation
        9. terse - keep brevity constraints close to the output
        10. checkpoint - periodic persona reinforcement
        11. state_block - session metadata appended last
    """
    base = get_base_prompt(product_context, strategy)
    state = (
        turn_state
        if turn_state is not None
        else analyse_state(history, user_message, signal_keywords=SIGNALS)
    )
    preferences = extract_preferences(history)

    # Tier 1: Override (early exit)
    override = check_override_condition(
        base, user_message, stage, history, preferences
    )
    if override:
        return override

    # ack level - must appear before the stage prompt
    ack_guidance = get_ack_guidance(detect_ack_context(user_message, history, state))

    # tactic guidance (adaptation for low-intent / guarded / decisive users)
    tactic_guidance = _build_tactic_guidance(strategy, state, user_message)

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
    budget_only_guard = ""
    if stage == Stage.INTENT and recent_assistant_question:
        repetition_guard = (
            "\nRECENT ASSISTANT QUESTION: "
            f"{recent_assistant_question}\n"
            "Do not repeat that question. Move forward with a fresh, natural question.\n"
        )

    # CRITICAL GUARD: Prevent pitching when user only mentioned budget/price without stating needs
    if stage == Stage.INTENT and user_message:
        user_text = user_message.lower()
        from .utils import contains_nonnegated_keyword
        has_budget_keywords = contains_nonnegated_keyword(
            user_text, ["budget", "price", "cost", "afford", "payment", "fee"]
        )
        has_problem_keywords = contains_nonnegated_keyword(
            user_text, ["need", "problem", "issue", "struggling", "looking for", "help with", "interested in"]
        )
        if has_budget_keywords and not has_problem_keywords:
            budget_only_guard = (
                "\nBUDGET-ONLY GUARD: User mentioned budget/price but has NOT stated their actual need or problem yet. "
                "Do NOT jump to product suggestions. Ask clarifying questions to understand:\n"
                "1. What problem/need brought them here\n"
                "2. What they're currently using/doing\n"
                "3. What's not working\n"
                "Only suggest products after you understand their situation.\n"
            )

    # tier 6: compute turn metadata (used later when injecting final state block)
    turn_count = len(history) // 2

    # Terse response handling: prevent over-probing short answers.
    # Keep terse guidance close to generation.
    terse_guidance = ""
    msg_len = len(user_message.split()) if user_message else 0
    if msg_len < TERSE_INPUT_THRESHOLD and stage != Stage.INTENT:
        terse_guidance = (
            "\nTERSE INPUT: Very short answer. Make ONE observation, then ONE question. "
            "Do not over-probe.\n"
        )

    # Periodic persona reinforcement: anchor every N turns using the constants
    persona_checkpoint = ""
    if turn_count > 0 and turn_count % PERSONA_CHECKPOINT_TURNS == 0:
        persona_checkpoint = (
            f"\n[CHECKPOINT - Turn {turn_count}]: Stay in {strategy} mode. "
            f"One question per turn. Current stage: {stage}.\n"
        )

    # Ordering rationale (effect of order):
    # - base anchors factual constraints via primacy.
    # - place ack and tactic guidance before the stage instruction so adaptation informs behaviour.
    # - place the stage_prompt later so it sits close to conversation content.
    # - keep history and terse guidance near the end to preserve recency.
    history_block = ""
    if include_history:
        history_block = (
            f"\nRECENT CONVERSATION:\n{format_conversation_context(history)}\n"
        )

    # Build `state_block` last so session metadata appears at the end
    state_block = f"""
=== TURN CONTEXT ===
Stage: {stage.upper()} | Strategy: {strategy.upper()} | Turn: {turn_count}
Intent: {state.intent} | Guarded: {"yes" if state.guarded else "no"}
=== END CONTEXT ===
"""

    # Final assembly: Deliberate Order
    return (
        base
        + ack_guidance
        + tactic_guidance
        + stage_prompt
        + stage_context
        + budget_only_guard
        + drift_note
        + repetition_guard
        + history_block
        + preference_keyword_context
        + terse_guidance
        + persona_checkpoint
        + state_block
    )
