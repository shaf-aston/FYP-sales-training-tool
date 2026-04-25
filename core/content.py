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
from .utils import contains_nonnegated_keyword

from .objection import _build_objection_context

ELICITATION_TACTICS = [
    "Most people in your situation feel trapped between their current setup and exploring new options. What's kept you from making a move so far?",
    "You've probably tried handling this yourself already. What's made that approach work for you up until now?",
    "I'm guessing this isn't urgent, but there's something nudging you to look at alternatives. What is it?",
]

def _build_tactic_guidance(strategy: str, state: Any, user_message: str) -> str:
    """Generate adaptive bot guidance based on user state.
    
    Applies different strategies for decisive vs. guarded users. Returns empty
    string if no special adaptation needed (user is engaged and open).
    """
    if state.decisive:
        return get_adaptation_template("decisive_user", strategy=strategy)

    if state.intent == "low" or state.guarded or state.question_fatigue:
        if is_literal_question(user_message):
            return get_adaptation_template("literal_question")

        # Determine reason for adaptation
        if state.intent == "low":
            reason = "low intent"
        elif state.guarded:
            reason = "guarded response"
        else:
            reason = "question fatigue (2+ recent questions)"

        # Get elicitation example if consultative
        elicitation_example = ""
        if strategy == "consultative":
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

def _get_stage_specific_prompt(
    strategy, stage, state, user_message, history, objection_data=None
):
    """Select stage-specific prompt and optionally build objection context.

    Intent stage uses low-intent variant if state indicates low buying signal.
    Objection stage is handled via _build_objection_context so SOP logic is centralized
    and reusable. Returns (prompt_string, context_block) so stage_context can be
    injected separately during final assembly (supports positional bias).
    """

    # Intent stage: pick low-intent or standard prompt
    if stage == "intent":
        prompt_key = "intent_low" if state.intent == "low" else "intent"
        return get_prompt(strategy, prompt_key), ""

    if stage in ("logical", "emotional"):
        return get_prompt(strategy, stage), ""

    # Objection stage is delegated to chatbot.objection so the rules live in one place
    if stage == "objection":
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
    pre_state=None,
    include_history: bool = True,
) -> str:
    """Build the full system prompt for this turn.
    Assembly order: base+rules -> ack -> tactics -> stage_prompt -> stage_context
                    -> drift_note -> history -> preferences -> terse -> checkpoint -> state_block
    Tactics precede the stage prompt so adaptation guidance informs stage behaviour.
    History and terse guidance sit late (recency bias).
    """
    base = get_base_prompt(product_context, strategy)
    state = (
        pre_state
        if pre_state is not None
        else analyse_state(history, user_message, signal_keywords=SIGNALS)
    )
    preferences = extract_preferences(history)

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

    # tier 6: compute turn metadata (used later when injecting final state block)
    turn_count = len(history) // 2

    # Terse response handling: prevent over-probing short answers.
    # Keep terse guidance close to generation.
    terse_guidance = ""
    msg_len = len(user_message.split()) if user_message else 0
    if msg_len < TERSE_INPUT_THRESHOLD and stage != "intent":
        terse_guidance = (
            "\nTERSE INPUT: Very short answer. Match their brevity. "
            "Use one short sentence or one short open question. "
            "No padded validation, no layered follow-up, no over-probing.\n"
        )

    # Periodic persona reinforcement: anchor every N turns using the constants
    persona_checkpoint = ""
    if turn_count > 0 and turn_count % PERSONA_CHECKPOINT_TURNS == 0:
        persona_checkpoint = f"\n[CHECKPOINT - Turn {turn_count}]: Stay in {strategy} mode. One question per turn. Current stage: {stage}.\n"

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
        + drift_note
        + history_block
        + preference_keyword_context
        + terse_guidance
        + persona_checkpoint
        + state_block
    )
