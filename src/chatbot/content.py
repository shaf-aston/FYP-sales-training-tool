"""Builds the final system prompt from templates, overrides, and tactics"""

from typing import Any

from .loader import (
    load_signals,
    load_objection_flows,
    get_adaptation_template,
    get_tactic,
    get_override_template,
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
    classify_objection,
    commitment_or_walkaway,
    is_repetitive_validation,
)
from .constants import PERSONA_CHECKPOINT_TURNS, TERSE_INPUT_THRESHOLD
from .utils import contains_nonnegated_keyword

from .objection import _build_objection_context

def _build_tactic_guidance(strategy: str, state: Any, user_message: str) -> str:
    """Return tactic guidance to adapt bot behaviour based on user state.

    Decisive users get a direct guidance template. Low-intent, guarded, or fatigued users
    trigger adaptive strategies. Literal questions are handled separately to avoid repeating
    questions. Consultative strategy includes elicitation examples; transactional does not.
    Returns empty string if no adaptation is needed (user is engaged and open).
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
            elicitation_example = get_tactic("elicitation", "combined")

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


def check_override_condition(base_prompt, user_message, stage, history, preferences):
    """Return an override prompt if user input matches a high-priority signal, else None.

    Overrides short-circuit the normal prompt assembly pipeline. Priority order:
    1. Direct info request (user demands facts immediately)
    2. Soft positive at pitch (user signals readiness; use assumptive close)
    3. Excessive validation (user repeating concerns; force substantive response)
    Each override is strategy and context-aware. None returned if no condition fires.
    """
    # Direct info request: user demands facts immediately. Override to provide data.
    direct_info_requests = SIGNALS.get("direct_info_requests", [])
    if contains_nonnegated_keyword(user_message, direct_info_requests):
        return get_override_template(
            "direct_info_request",
            base=base_prompt,
            preferences=preferences or "not yet specified",
        )

    # Soft positive at pitch: user shows readiness. Use assumptive close to capture intent.
    soft_positive_signals = SIGNALS.get("soft_positive", [])
    if (
        contains_nonnegated_keyword(user_message, soft_positive_signals)
        and stage == "pitch"
    ):
        return get_override_template(
            "soft_positive_at_pitch",
            base=base_prompt,
            user_message=user_message,
            preferences=preferences or "price, reliability, features",
        )

    # Excessive validation: user repeating concerns. Force substantive response.
    if is_repetitive_validation(history):
        return get_override_template(
            "excessive_validation",
            base=base_prompt,
            preferences=preferences or "Not yet extracted",
        )

    return None


def generate_stage_prompt(
    strategy: str,
    stage: str,
    product_context: str,
    history: list[dict[str, str]],
    user_message: str = "",
    objection_data: dict | None = None,
    pre_state=None,
) -> str:
    """Build the full system prompt for this turn.
    Assembly order (ordering effect: later items have greater influence on generation):
    base+rules -> ack -> tactics -> stage_prompt -> stage_context -> drift_note -> history -> preferences -> terse -> checkpoint -> state_block
    Overrides short-circuit the pipeline and return immediately.
    Place tactics before the stage prompt so adaptation guidance is included in the stage instruction.
    Keep history and terse guidance close to generation to preserve recency.
    """
    base = get_base_prompt(product_context, strategy)
    state = (
        pre_state
        if pre_state is not None
        else analyse_state(history, user_message, signal_keywords=SIGNALS)
    )
    preferences = extract_preferences(history)

    # tier 1: overrides take priority. Return override immediately if one fires
    override = check_override_condition(base, user_message, stage, history, preferences)
    if override:
        return override

    # tier 2: ack level. Must appear before the stage prompt
    ack_guidance = get_ack_guidance(detect_ack_context(user_message, history, state))

    # tier 3: tactic guidance
    tactic_guidance = _build_tactic_guidance(strategy, state, user_message)

    # tier 4: stage prompt
    stage_prompt, stage_context = _get_stage_specific_prompt(
        strategy, stage, state, user_message, history, objection_data
    )

    # tier 5: assemble final prompt blocks
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
        terse_guidance = "\nTERSE INPUT: Very short answer. Make ONE observation, then ONE question. Do not over-probe.\n"

    # Periodic persona reinforcement: anchor every N turns using the constants
    persona_checkpoint = ""
    if turn_count > 0 and turn_count % PERSONA_CHECKPOINT_TURNS == 0:
        persona_checkpoint = f"\n[CHECKPOINT — Turn {turn_count}]: Stay in {strategy} mode. One question per turn. Current stage: {stage}.\n"

    # Ordering rationale (effect of order):
    # - base anchors factual constraints via primacy.
    # - place ack and tactic guidance before the stage instruction so adaptation informs behaviour.
    # - place the stage_prompt later so it sits close to conversation content.
    # - keep history and terse guidance near the end to preserve recency.
    history_block = f"\nRECENT CONVERSATION:\n{format_conversation_context(history)}\n"

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
