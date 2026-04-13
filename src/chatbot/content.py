"""Builds the final system prompt from templates, overrides, and tactics"""

from .loader import loadSIGNALS, load_objection_flows
from .prompts import (
    get_prompt,
    generate_init_greeting,
    get_base_prompt,
    get_acknowledgment_guidance,
    format_conversation_context,
)
from .overrides import check_override_condition
from .loader import get_adaptation_template, get_tactic
from .analysis import (
    analyse_state,
    extract_preferences,
    detect_acknowledgment_context,
    extract_user_keywords,
    is_literal_question,
    classify_objection,
    commitment_or_walkaway,
)
from .constants import PERSONA_CHECKPOINT_TURNS, TERSE_INPUT_THRESHOLD

OFLOWS = load_objection_flows()
SOP_FLOWS = OFLOWS.get("sop_flows", {})
SOP_FLOWS_TRANSACTIONAL = {**SOP_FLOWS, **OFLOWS.get("transactional_overrides", {})}
SOP_FLOW_FALLBACK = OFLOWS.get(
    "fallback",
    "1. Acknowledge\n2. Recall stated goal\n3. Apply reframe strategy\n4. Ask ONE question",
)


def build_objection_context(strategy, stage, user_message, history, objection_data=None):
    """Build SOP context block for objection stage only"""
    stage_value = getattr(stage, "value", stage)
    if str(stage_value).lower() != "objection" or not user_message:
        return ""

    if commitment_or_walkaway(history, user_message, 0):
        return ""

    info = objection_data if isinstance(objection_data, dict) else classify_objection(user_message, history)
    if info.get("type") == "unknown":
        return ""

    flows = SOP_FLOWS_TRANSACTIONAL if strategy == "transactional" else SOP_FLOWS
    steps = flows.get(info["type"], SOP_FLOW_FALLBACK)

    return (
        f"OBJECTION CLASSIFIED: {info['type'].upper()}\n"
        f"REFRAME STRATEGY: {info['strategy']}\n"
        f"GUIDANCE: {info['guidance']}\n\n"
        f"STEPS:\n{steps}\n"
    )
from typing import Any


def build_tactic_guidance(strategy: str, state: Any, user_message: str) -> str:
    """Tactic guidance string based on user state and strategy"""
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
            elicitation_example=elicitation_example
        )

    return ""

# Exported signals for consumers (e.g. flow.py)
SIGNALS = loadSIGNALS()

# Export public symbols
__all__ = ["generate_stage_prompt", "generate_init_greeting", "get_prompt", "SIGNALS"]


def _get_preference_and_keyword_context(history, preferences):
    """Extract and format user preferences and keywords for prompt context"""
    preference_context = f"\nUSER PREFERENCES: {preferences}\nUSE these to personalize your response." if preferences else ""
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
    """Pick stage prompt and build any objection context block"""

    # Intent stage: pick low-intent or standard prompt
    if stage == "intent":
        prompt_key = "intent_low" if state.intent == "low" else "intent"
        return get_prompt(strategy, prompt_key), ""

    if stage in ("logical", "emotional"):
        return get_prompt(strategy, stage), ""

    # Objection stage is delegated to chatbot.objection so the rules live in one place
    if stage == "objection":
        objection_context = build_objection_context(
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
) -> str:
    """Build the full system prompt for this turn. overrides → ack → tactics → stage → state → assembly"""
    base = get_base_prompt(product_context, strategy)
    state = pre_state if pre_state is not None else analyse_state(history, user_message, signal_keywords=SIGNALS)
    preferences = extract_preferences(history)

    # tier 1: overrides take priority — bail early if one fires
    override = check_override_condition(base, user_message, stage, history, preferences)
    if override:
        return override

    # tier 2: ack level — must come before the stage prompt
    ack_guidance = get_acknowledgment_guidance(
        detect_acknowledgment_context(user_message, history, state)
    )

    # tier 3: tactic guidance
    tactic_guidance = build_tactic_guidance(strategy, state, user_message)

    # tier 4: stage prompt
    stage_prompt, stage_context = _get_stage_specific_prompt(strategy, stage, state, user_message, history, objection_data)

    # tier 5: assemble
    preference_keyword_context = _get_preference_and_keyword_context(history, preferences)

    # tier 6: inject turn context
    turn_count = len(history) // 2

    state_block = f"""
=== TURN CONTEXT ===
Stage: {stage.upper()} | Strategy: {strategy.upper()} | Turn: {turn_count}
Intent: {state.intent} | Guarded: {'yes' if state.guarded else 'no'}
=== END CONTEXT ===
"""

    # Terse response handling — prevent over-probing short answers
    terse_guidance = ""
    msg_len = len(user_message.split()) if user_message else 0
    if msg_len < TERSE_INPUT_THRESHOLD and stage != "intent":
        terse_guidance = "\nTERSE INPUT: Very short answer. Make ONE observation, then ONE question. Do not over-probe.\n"

    # Periodic persona reinforcement (anchor every N turns from constants)
    persona_checkpoint = ""
    if turn_count > 0 and turn_count % PERSONA_CHECKPOINT_TURNS == 0:
        persona_checkpoint = f"\n[CHECKPOINT — Turn {turn_count}]: Stay in {strategy} mode. One question per turn. Current stage: {stage}.\n"

    # Ordering rationale (positional bias):
    # base (product/strategy/rules) anchors factual constraints via primacy
    # stage_prompt lands late — benefits from recency, LLM reads instruction then immediately sees the conversation
    # history injected after stage instruction — user's last words are freshest at generation time
    history_block = f"\nRECENT CONVERSATION:\n{format_conversation_context(history)}\n"
    return (base + state_block + ack_guidance + stage_prompt + stage_context +
            history_block + tactic_guidance + preference_keyword_context +
            terse_guidance + persona_checkpoint)
