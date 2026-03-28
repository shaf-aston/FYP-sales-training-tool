"""Prompt assembly and orchestration.

Combines templates (prompts.py), intervention logic (overrides.py),
and tactical adaptations (tactics.py) into the final system prompt.
"""

from typing import Any
from .loader import load_signals
from .prompts import (
    get_prompt,
    generate_init_greeting,
    get_base_prompt,
    get_acknowledgment_guidance
)
from .overrides import check_override_condition
from .tactics import build_tactic_guidance
from .analysis import (
    analyze_state,
    extract_preferences,
    detect_acknowledgment_context,
    classify_objection,
    extract_user_keywords,
    commitment_or_walkaway
)
from .constants import PERSONA_CHECKPOINT_TURNS, TERSE_INPUT_THRESHOLD

# Exported signals for consumers (e.g. flow.py)
SIGNALS = load_signals()

# Re-export for compatibility
__all__ = ["generate_stage_prompt", "generate_init_greeting", "get_prompt", "SIGNALS"]


def _get_preference_and_keyword_context(history, preferences):
    """Extract and format user preferences and keywords for prompt context."""
    preference_context = f"\nUSER PREFERENCES: {preferences}\nUSE these to personalize your response." if preferences else ""
    
    # We need to make sure extract_user_keywords is imported - added it above
    user_keywords = extract_user_keywords(history)
    keyword_context = ""
    if user_keywords:
        keyword_context = f"""
USER'S OWN WORDS (embed keywords, don't replay sentences):
Terms the user has used: {', '.join(user_keywords)}
Naturally embed 1-2 into your response. Do NOT replay full sentences.
"""

    return preference_context + keyword_context


def _get_stage_specific_prompt(strategy, stage, state, user_message, history, objection_data=None):
    """Get stage-specific prompt with any special handling (intent_low, objection classification).

    Args:
        objection_data: Pre-computed objection classification (avoids redundant classify_objection calls)
    """

    # Intent stage: pick low-intent or standard prompt
    if stage == "intent":
        prompt_key = "intent_low" if state.intent == "low" else "intent"
        return get_prompt(strategy, prompt_key), ""

    # Objection stage: classify and inject reframe guidance
    if stage == "objection" and user_message:
        # Check if user is walking — no reframe needed
        if commitment_or_walkaway(history, user_message, 0):
            return get_prompt(strategy, stage), ""  # user is walking — no reframe needed

        # Use pre-computed objection_data if provided, otherwise compute
        objection_info = objection_data if objection_data else classify_objection(user_message, history)
        if objection_info["type"] != "unknown":
            # Map type to acknowledgment instruction
            ack_map = {
                "fear":        "1. Full acknowledgment: validate the concern (1 sentence) — they need to feel heard before reframing",
                "money":       "1. Light acknowledgment: 'I hear you.' — then go straight to reframe",
                "think":       "1. Light acknowledgment: 'Totally fair.' — then drill to the real concern",
                "partner":     "1. Light acknowledgment: 'Makes sense.' — shows respect for their process",
                "logistical":  "1. SKIP acknowledgment — solve the logistics directly, no preamble",
                "smokescreen": "1. SKIP acknowledgment — test if genuine first: 'Is it the product itself, or something else?'",
            }
            # Fallback
            _ack_step = ack_map.get(objection_info["type"], "1. Light acknowledgment only if concern feels genuine — otherwise reframe directly")
            
            objection_context = f"""
OBJECTION CLASSIFIED: {objection_info['type'].upper()}
REFRAME STRATEGY: {objection_info['strategy']}
GUIDANCE: {objection_info['guidance']}

STEPS:
{_ack_step}
2. Recall the user's stated goal/problem from earlier
3. Apply the reframe strategy above
4. Ask ONE question to move forward
"""
            return get_prompt(strategy, stage), objection_context
    
    # Default: standard stage prompt
    return get_prompt(strategy, stage), ""


def generate_stage_prompt(
    strategy: str,
    stage: str,
    product_context: str,
    history: list[dict[str, str]],
    user_message: str = "",
    objection_data: dict | None = None,
) -> str:
    """Build the full system prompt for the current turn.

    4-tier routing:
    1. OVERRIDES: Direct requests, soft positives, validation loops (immediate return)
    2. ADAPTATIONS: Decisive users, literal questions, low-intent/guarded (tactical guidance)
    3. STAGE SELECT: intent_low vs intent, objection classification
    4. ASSEMBLY: base + stage + adaptations + preferences + keywords

    Args:
        objection_data: Pre-computed objection classification (avoids redundant calls)
    """
    # Build base prompt and analyze state
    base = get_base_prompt(product_context, strategy, history)
    state = analyze_state(history, user_message, signal_keywords=SIGNALS)
    preferences = extract_preferences(history)

    # TIER 1: Check for override conditions (highest priority - early return)
    override = check_override_condition(base, user_message, stage, history, preferences)
    if override:
        return override

    # TIER 2: Acknowledgment decision (must precede stage prompt so LLM sees it first)
    ack_guidance = get_acknowledgment_guidance(
        detect_acknowledgment_context(user_message, history, state)
    )

    # TIER 3: Build adaptive tactic guidance
    tactic_guidance = build_tactic_guidance(strategy, state, user_message)

    # TIER 4: Get stage-specific prompt
    stage_prompt, stage_context = _get_stage_specific_prompt(strategy, stage, state, user_message, history, objection_data)

    # TIER 5: Assemble final prompt
    preference_keyword_context = _get_preference_and_keyword_context(history, preferences)

    # TIER 6: Dynamic context injection (structured state + preprocessing)
    turn_count = len(history) // 2

    state_block = f"""
=== TURN CONTEXT ===
Stage: {stage.upper()} | Strategy: {strategy.upper()} | Turn: {turn_count}
Intent: {state.intent} | Guarded: {'yes' if state.guarded else 'no'}
=== END CONTEXT ===
"""

    # Terse response handling — prevent over-probing short answers
    terse_guidance = ""
    # Safe null check
    msg_len = len(user_message.split()) if user_message else 0
    if msg_len < TERSE_INPUT_THRESHOLD and stage != "intent":
        terse_guidance = "\nTERSE INPUT: Very short answer. Make ONE observation, then ONE question. Do not over-probe.\n"

    # Periodic persona reinforcement (anchor every N turns from constants)
    persona_checkpoint = ""
    if turn_count > 0 and turn_count % PERSONA_CHECKPOINT_TURNS == 0:
        persona_checkpoint = f"\n[CHECKPOINT — Turn {turn_count}]: Stay in {strategy} mode. One question per turn. Current stage: {stage}.\n"

    # Strict ordering: Base -> State -> Ack -> Stage -> Strategy Specific -> Tactics -> Preferences -> Terse -> Checkpoint
    return base + state_block + ack_guidance + stage_prompt + stage_context + tactic_guidance + preference_keyword_context + terse_guidance + persona_checkpoint
