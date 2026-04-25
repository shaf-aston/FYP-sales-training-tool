"""Objection analysis engine: classification, pathway detection and reframe sequencing."""

import logging
import warnings
from typing import Any, Optional, TypedDict

from .constants_enums import MessageRole, ObjectionType
from .helpers import HistoryHelper
from .loader import load_analysis_config, load_objection_flows, load_yaml
from .utils import contains_nonnegated_keyword

logger = logging.getLogger(__name__)

ANALYSIS_CONFIG = load_analysis_config()
OBJECTION_FLOWS_CONFIG = load_objection_flows()

OBJECTION_FLOWS = OBJECTION_FLOWS_CONFIG.get("sop_flows", {})
# Transactional flows override standard flows when applicable
OBJECTION_FLOWS_TRANSACTIONAL = {
    **OBJECTION_FLOWS,
    **OBJECTION_FLOWS_CONFIG.get("transactional_overrides", {}),
}
OBJECTION_FLOW_FALLBACK = OBJECTION_FLOWS_CONFIG.get(
    "fallback",
    "1. Acknowledge\n2. Recall stated goal\n3. Apply reframe strategy\n4. Ask ONE question",
)

class ObjectionPathway(TypedDict):
    """Result of objection analysis with type, strategy and reframe pathway.

    Contains both the objection classification and the recommended reframe sequence.
    """
    type: str
    strategy: str
    guidance: str
    category: str
    subtype: str
    entry_question: str
    reframes: list[str]
    reframe_descriptions: dict[str, dict[str, str]]
    funding_options: list[str]
    open_wallet_applicable: bool
    dialogue_guidance: str
    is_primary_objection: bool

def _extract_recent_user_messages(
    history: Optional[list[dict]], max_messages: int = 2
) -> list[str]:
    """Extract recent user messages from history.

    Simplifies the common pattern of getting N most recent user message texts.
    """
    return HistoryHelper.get_recent_user_messages(history, count=max_messages)


def classify_objection(
    user_message: str, history: Optional[list[dict]] = None
) -> dict[str, Any]:
    """Classify objection type and pick a reframe"""
    objection_config = ANALYSIS_CONFIG.get("objection_handling", {})
    classification_order = objection_config.get(
        "classification_order",
        [
            ObjectionType.SMOKESCREEN,
            ObjectionType.PARTNER,
            ObjectionType.MONEY,
            ObjectionType.FEAR,
            ObjectionType.LOGISTICAL,
            ObjectionType.THINK,
        ],
    )
    objection_keywords = OBJECTION_FLOWS_CONFIG.get("keywords", {})
    reframe_guidance = OBJECTION_FLOWS_CONFIG.get("reframe_guidance", {})

    def _classify_text(text: str) -> Optional[dict[str, Any]]:
        for obj_type in classification_order:
            keywords = objection_keywords.get(obj_type, [])
            if not contains_nonnegated_keyword(text, keywords):
                continue

            strategies = objection_config.get("reframe_strategies", {}).get(
                obj_type, []
            )
            # Deterministic strategy selection
            strategy_name = strategies[0] if strategies else "general_reframe"
            guidance = reframe_guidance.get(obj_type, {}).get(
                strategy_name,
                f"Address the {obj_type} concern directly using the user's stated goals.",
            )
            return {"type": obj_type, "strategy": strategy_name, "guidance": guidance}
        return None

    user_message_lower = user_message.lower()

    # Prefer current-turn signals to avoid stale history overriding fresh objections.
    current_match = _classify_text(user_message_lower)
    if current_match is not None:
        return current_match

    if history:
        recent_user = _extract_recent_user_messages(history, max_messages=2)
        if recent_user and recent_user[-1] == user_message_lower:
            recent_user = recent_user[:-1]
        combined = HistoryHelper.combine_messages(recent_user + [user_message_lower]).strip()
        history_match = _classify_text(combined)
        if history_match is not None:
            return history_match

    return {
        "type": ObjectionType.UNKNOWN,
        "strategy": "general_reframe",
        "guidance": "Acknowledge the concern. Recall the user's stated goal. Ask what specifically is holding them back.",
    }

# ============================================================================
# PATHWAY ANALYSIS
# ============================================================================

_PATHWAY_CONFIG = None


def _load_pathway_config() -> dict[str, Any]:
    global _PATHWAY_CONFIG
    if _PATHWAY_CONFIG is None:
        try:
            _PATHWAY_CONFIG = load_yaml("objection_pathway_map.yaml")
        except Exception as e:
            warnings.warn(f"Failed to load objection_pathway_map.yaml: {e}")
            _PATHWAY_CONFIG = {"category_mapping": {}, "reframe_descriptions": {}}
    return _PATHWAY_CONFIG


def validate_pathway_config() -> tuple[bool, list[str]]:
    pathway_config = _load_pathway_config()
    errors = []

    category_mapping = pathway_config.get("category_mapping", {})
    if not category_mapping:
        errors.append("category_mapping is empty or missing")
        return False, errors

    for category_name, category_data in category_mapping.items():
        entry_question = category_data.get("entry_question", "")
        if not entry_question or len(entry_question.strip()) == 0:
            errors.append(f"Category '{category_name}' has empty entry_question")

        reframes = category_data.get("reframes", [])
        if category_name != "unclear" and len(reframes) == 0:
            errors.append(f"Category '{category_name}' has no reframes")

        if category_name == "resource":
            funding_options = category_data.get("funding_options", [])
            if len(funding_options) < 3:
                errors.append(
                    f"Category 'resource' should have 3+ funding options, got {len(funding_options)}"
                )

    reframe_descriptions = pathway_config.get("reframe_descriptions", {})
    required_reframes = ["change_of_process", "island_mountain", "identity_loop"]
    for reframe_id in required_reframes:
        if reframe_id not in reframe_descriptions:
            errors.append(f"Reframe '{reframe_id}' missing from reframe_descriptions")
        else:
            description = reframe_descriptions[reframe_id]
            for key in ["title", "dialogue", "example", "check_question"]:
                if key not in description or not description[key]:
                    errors.append(f"Reframe '{reframe_id}' missing or empty '{key}'")

    type_mapping = pathway_config.get("type_to_category_mapping", {})
    old_types = ["money", "partner", "fear", "logistical", "think", "smokescreen", "unknown"]
    for old_type in old_types:
        if old_type not in type_mapping:
            errors.append(f"Old type '{old_type}' not in type_to_category_mapping")

    return len(errors) == 0, errors


def _validate_on_import():
    is_valid, errors = validate_pathway_config()
    if not is_valid:
        warnings.warn(
            "Pathway config validation errors: " + "; ".join(errors),
            category=UserWarning,
        )

_validate_on_import()


def _detect_subtype(category: str, user_message: str, objection_type: str) -> str:
    pathway_config = _load_pathway_config()
    category_data = pathway_config.get("category_mapping", {}).get(category, {})
    subtypes = category_data.get("subtypes", [])

    user_message_lower = user_message.lower()
    best_match = None
    max_matches = 0

    for subtype_info in subtypes:
        subtype_id = subtype_info.get("id", "")
        indicators = subtype_info.get("indicators", [])

        matches = sum(1 for indicator in indicators if indicator.lower() in user_message_lower)
        if matches > max_matches:
            max_matches = matches
            best_match = subtype_id

    if best_match is None and subtypes:
        best_match = subtypes[0].get("id", "unknown")

    return best_match or "unspecified"

def _build_pathway_metadata(base_dict: dict[str, Any], user_message: str) -> ObjectionPathway:
    pathway_config = _load_pathway_config()
    type_to_category = pathway_config.get("type_to_category_mapping", {})
    category_mapping = pathway_config.get("category_mapping", {})
    reframe_descriptions = pathway_config.get("reframe_descriptions", {})

    objection_type = str(base_dict.get("type", "unknown"))
    category = str(type_to_category.get(objection_type, "unclear"))
    category_data = category_mapping.get(category, {})

    subtype = _detect_subtype(category, user_message, objection_type)

    reframe_descriptions_dict: dict[str, dict[str, str]] = {}
    reframes = [str(reframe_id) for reframe_id in category_data.get("reframes", [])]
    for reframe_id in reframes:
        if reframe_id in reframe_descriptions:
            description_data = reframe_descriptions[reframe_id]
            reframe_descriptions_dict[reframe_id] = {
                "title": str(description_data.get("title", "")),
                "dialogue": str(description_data.get("dialogue", "")),
                "example": str(description_data.get("example", "")),
                "check_question": str(description_data.get("check_question", "")),
            }

    funding_options: list[str] = []
    if category == "resource":
        funding_options = [
            str(option) for option in category_data.get("funding_options", [])
        ]

    open_wallet_applicable = bool(
        category_data.get("open_wallet_applicable", False)
    )

    pathway: ObjectionPathway = {
        "type": objection_type,
        "strategy": str(base_dict.get("strategy", "general_reframe")),
        "guidance": str(base_dict.get("guidance", "")),
        "category": category,
        "subtype": subtype,
        "entry_question": str(category_data.get("entry_question", "")),
        "reframes": reframes,
        "reframe_descriptions": reframe_descriptions_dict,
        "funding_options": funding_options,
        "open_wallet_applicable": open_wallet_applicable,
        "dialogue_guidance": str(category_data.get("dialogue_guidance", "")),
        "is_primary_objection": True,
    }

    return pathway

def analyse_objection_pathway(
    user_message: str,
    history: Optional[list[dict]] = None,
    attempt_count: int = 0,
    conversation_context: Optional[dict] = None,
) -> ObjectionPathway:
    base_dict = classify_objection(user_message, history)
    pathway = _build_pathway_metadata(base_dict, user_message)
    return pathway

def _count_reframe_usages(
    reframes: list[str],
    history: Optional[list[dict]] = None,
) -> dict[str, int]:
    """Count how many times each reframe has been used in conversation.

    Args:
        reframes: List of reframe IDs to track
        history: Conversation history

    Returns:
        Dictionary mapping reframe_id to usage count
    """
    attempts = {reframe_id: 0 for reframe_id in reframes}

    if not history:
        return attempts

    for msg in history:
        if msg.get("role") == MessageRole.ASSISTANT:
            content = msg.get("content", "").lower()
            for reframe_id in reframes:
                if f"reframe_{reframe_id}" in content:
                    attempts[reframe_id] += 1

    return attempts


def _find_next_reframe_index(
    reframes: list[str],
    reframe_usages: dict[str, int],
) -> int:
    """Find index of next reframe to use (first unused, or end if all used).

    Args:
        reframes: List of reframe IDs in order
        reframe_usages: Dictionary of usage counts per reframe

    Returns:
        Index of next reframe to use
    """
    for i, reframe_id in enumerate(reframes):
        if reframe_usages.get(reframe_id, 0) == 0:
            return i

    # All reframes have been tried
    return len(reframes)


def get_reframe_sequence(
    pathway: ObjectionPathway,
    current_turn_in_stage: int,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Get the current reframe to use and tracking metadata.

    Args:
        pathway: Objection pathway with reframe sequence
        current_turn_in_stage: Current turn number (for context)
        history: Conversation history

    Returns:
        Dictionary with current reframe, index, attempts and guidance
    """
    reframes = pathway.get("reframes", [])
    reframe_descriptions = pathway.get("reframe_descriptions", {})

    if not reframes:
        return {
            "current_reframe": None,
            "reframe_index": 0,
            "attempts_so_far": 0,
            "next_check_question": "Does that make sense?",
            "is_final_reframe": False,
        }

    reframe_usages = _count_reframe_usages(reframes, history)
    current_index = _find_next_reframe_index(reframes, reframe_usages)
    current_reframe = reframes[current_index] if current_index < len(reframes) else None

    next_check_question = ""
    if current_reframe:
        reframe_desc = reframe_descriptions.get(current_reframe, {})
        next_check_question = reframe_desc.get("check_question", "Does that make sense?")

    return {
        "current_reframe": current_reframe,
        "reframe_index": current_index,
        "attempts_so_far": (
            reframe_usages.get(current_reframe, 0) if current_reframe else 0
        ),
        "next_check_question": next_check_question,
        "is_final_reframe": (
            current_index >= len(reframes) - 1 if current_reframe else False
        ),
    }

def _get_objection_pathway_safe(
    user_message: str, history: list[dict]
) -> dict[str, Any]:
    """Get objection pathway with graceful fallback to classify_objection."""
    try:
        return dict(analyse_objection_pathway(user_message, history))
    except Exception as e:
        logger.debug(f"Pathway analysis failed, falling back: {e}")
        return classify_objection(user_message, history)


def _count_objection_attempts(history: list[dict] | None, obj_type: str) -> int:
    """Count how many times the assistant has already responded to this objection.

    Finds the most recent user message with matching objection keywords, then counts
    assistant messages after that point. Returns 0 on first hit.
    """
    if not history:
        return 0
    keywords = OBJECTION_FLOWS_CONFIG.get("keywords", {}).get(obj_type, [])
    if not keywords:
        return 0
    most_recent_idx = None
    for i, msg in enumerate(history):
        if msg.get("role") == MessageRole.USER:
            content = msg.get("content", "").lower()
            if any(kw in content for kw in keywords):
                most_recent_idx = i
    if most_recent_idx is None:
        return 0
    return sum(
        1 for msg in history[most_recent_idx + 1:]
        if msg.get("role") == MessageRole.ASSISTANT
    )


def _build_resource_block(info: dict) -> str:
    block = "\n=== RESOURCE PATHWAY ===\n"
    dialogue_guidance = info.get("dialogue_guidance", "")
    if dialogue_guidance:
        block += dialogue_guidance.strip() + "\n"
    funding_options = info.get("funding_options", [])
    if funding_options:
        block += f"Options: {', '.join(funding_options)}\n"
    if info.get("open_wallet_applicable"):
        block += "[OPEN WALLET TEST: Confirm readiness is genuine aside from funds.]\n"
    return block


def _build_consultative_reframe_block(info: dict, attempt: int) -> str:
    """
    CONSULTATIVE DECISION MATRIX
    ─────────────────────────────────────────────────────────────
    attempt 0  →  Acknowledge + Entry Question only  (no reframe)
    attempt 1  →  reframes[0] + check question
    attempt 2  →  reframes[1] + check question
    attempt 3  →  reframes[2] + check question
    attempt 4+ →  All reframes used - final decision offer
    ─────────────────────────────────────────────────────────────
    """
    entry_question = info.get("entry_question", "")
    reframes = info.get("reframes", [])
    reframe_descriptions = info.get("reframe_descriptions", {})

    if attempt == 0:
        block = "\n[FIRST HIT - Acknowledge and ask the entry question. Do NOT reframe yet.]\n"
        if entry_question:
            block += f"ENTRY QUESTION: {entry_question}\n"
        return block

    reframe_idx = attempt - 1
    if not reframes or reframe_idx >= len(reframes):
        return "\n[FINAL - All reframes used. Make a clear close offer or acknowledge the objection is unresolvable.]\n"

    current_reframe_id = reframes[reframe_idx]
    reframe_desc = reframe_descriptions.get(current_reframe_id, {})
    is_final = reframe_idx >= len(reframes) - 1

    label = f"REFRAME {reframe_idx + 1}/{len(reframes)}"
    if is_final:
        label += " - FINAL REFRAME"
    block = f"\n[{label}]\n"
    block += f"REFRAME: {reframe_desc.get('title', current_reframe_id)}\n"
    block += f"DIALOGUE: {reframe_desc.get('dialogue', '').strip()}\n"
    block += f"EXAMPLE: {reframe_desc.get('example', '').strip()}\n"
    block += f"CHECK QUESTION: {reframe_desc.get('check_question', '').strip()}\n"

    if info.get("category") == "resource":
        block += _build_resource_block(info)

    return block


def _build_transactional_reframe_block(info: dict, attempt: int) -> str:
    """
    TRANSACTIONAL DECISION MATRIX
    ─────────────────────────────────────────────────────────────
    attempt 0  →  Acknowledge + clarify blocker + concise next step  (no reframe)
    attempt 1  →  One brief reframe + next step
    attempt 2+ →  Final direct close attempt
    ─────────────────────────────────────────────────────────────
    """
    reframes = info.get("reframes", [])
    reframe_descriptions = info.get("reframe_descriptions", {})

    if attempt == 0:
        return "\n[TRANSACTIONAL - Keep short. Acknowledge, clarify the blocker, offer the next step.]\n"

    if attempt >= 2 or not reframes:
        return "\n[TRANSACTIONAL FINAL - Direct close attempt or acknowledge a clear no.]\n"

    current_reframe_id = reframes[0]
    reframe_desc = reframe_descriptions.get(current_reframe_id, {})

    block = "\n[TRANSACTIONAL REFRAME - keep concise]\n"
    block += f"REFRAME: {reframe_desc.get('title', current_reframe_id)}\n"
    block += f"DIALOGUE: {reframe_desc.get('dialogue', '').strip()}\n"
    block += f"CHECK QUESTION: {reframe_desc.get('check_question', '').strip()}\n"
    return block


def _build_objection_context(
    strategy, stage, user_message, history, objection_data=None
):
    from .analysis import commitment_or_walkaway

    stage_value = getattr(stage, "value", stage)
    if str(stage_value).lower() != "objection" or not user_message:
        return ""

    if commitment_or_walkaway(history, user_message, 0):
        return ""

    # Use full pathway so category/reframes/entry_question are always available.
    if isinstance(objection_data, dict) and "category" in objection_data:
        info = objection_data
    else:
        info = _get_objection_pathway_safe(user_message, history)

    obj_type = info.get("type", ObjectionType.UNKNOWN)
    if obj_type == ObjectionType.UNKNOWN:
        return (
            "OBJECTION SIGNAL: UNCLEAR\n"
            "GUIDANCE: Do not reframe yet. Ask one direct question to surface the real concern.\n"
        )

    flows = OBJECTION_FLOWS_TRANSACTIONAL if strategy == "transactional" else OBJECTION_FLOWS
    sop_steps = flows.get(obj_type, OBJECTION_FLOW_FALLBACK)
    attempt = _count_objection_attempts(history, obj_type)

    context = (
        f"OBJECTION: {obj_type.upper()}\n"
        f"CATEGORY: {info.get('category', '').upper()}\n"
        f"STRATEGY: {info.get('strategy', 'general_reframe')}\n"
        f"GUIDANCE: {info.get('guidance', '')}\n\n"
        f"SOP STEPS:\n{sop_steps}\n"
    )

    if strategy == "transactional":
        context += _build_transactional_reframe_block(info, attempt)
    else:
        context += _build_consultative_reframe_block(info, attempt)

    return context
