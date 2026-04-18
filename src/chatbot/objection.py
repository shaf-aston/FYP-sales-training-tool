import logging
import warnings
from typing import Any, TypedDict, Optional

from .loader import load_analysis_config, load_objection_flows, load_yaml
from .utils import contains_nonnegated_keyword

_base_logger = logging.getLogger(__name__)

ANALYSIS_CONFIG = load_analysis_config()
OFLOWS = load_objection_flows()

SOP_FLOWS = OFLOWS.get("sop_flows", {})
# Transactional flows overlay standard ones
SOP_FLOWS_TRANSACTIONAL = {**SOP_FLOWS, **OFLOWS.get("transactional_overrides", {})}
SOP_FLOW_FALLBACK = OFLOWS.get(
    "fallback",
    "1. Acknowledge\n2. Recall stated goal\n3. Apply reframe strategy\n4. Ask ONE question",
)

class ObjectionPathway(TypedDict):
    """Rich objection analysis including pathway, reframes, entry questions.

    Base keys (backward compatible with classify_objection):
    - type: Original classification (money, partner, fear, etc.)
    - strategy: Reframe strategy name
    - guidance: LLM-ready guidance text

    Enhanced keys:
    - category: Barrier classification (resource, stakeholder, internal, unclear)
    - subtype: Specific barrier within category
    - entry_question: Leading question for this barrier
    - reframes: Required sequence of reframes [R1, R2, R3]
    - reframe_descriptions: Full details for each reframe
    - funding_options: Options for resource barriers
    - open_wallet_applicable: True if Open Wallet Test applies
    - dialogue_guidance: Specific instructions for guiding response
    - is_primary_objection: True if evaluated as core objection
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


def classify_objection(user_message: str, history: Optional[list[dict]] = None) -> dict[str, Any]:
    """classify objection type and pick a reframe"""
    objection_config = ANALYSIS_CONFIG.get("objection_handling", {})
    classification_order = objection_config.get(
        "classification_order",
        ["smokescreen", "partner", "money", "fear", "logistical", "think"],
    )
    objection_keywords = OFLOWS.get("keywords", {})
    reframe_guidance = OFLOWS.get("reframe_guidance", {})

    msg_lower = user_message.lower()
    combined = msg_lower
    if history:
        recent_user = [
            m["content"].lower() for m in history[-4:] if m["role"] == "user"
        ]
        if recent_user and recent_user[-1] == msg_lower:
            recent_user = recent_user[:-1]
        combined = " ".join(recent_user) + " " + msg_lower

    for obj_type in classification_order:
        keywords = objection_keywords.get(obj_type, [])
        if contains_nonnegated_keyword(combined, keywords):
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

    return {
        "type": "unknown",
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
        entry_q = category_data.get("entry_question", "")
        if not entry_q or len(entry_q.strip()) == 0:
            errors.append(f"Category '{category_name}' has empty entry_question")

        reframes = category_data.get("reframes", [])
        if category_name != "unclear" and len(reframes) == 0:
            errors.append(f"Category '{category_name}' has no reframes")

        if category_name == "resource":
            funding_opts = category_data.get("funding_options", [])
            if len(funding_opts) < 3:
                errors.append(f"Category 'resource' should have 3+ funding options, got {len(funding_opts)}")

    reframe_descriptions = pathway_config.get("reframe_descriptions", {})
    required_reframes = ["change_of_process", "island_mountain", "identity_loop"]
    for reframe_id in required_reframes:
        if reframe_id not in reframe_descriptions:
            errors.append(f"Reframe '{reframe_id}' missing from reframe_descriptions")
        else:
            desc = reframe_descriptions[reframe_id]
            for key in ["title", "dialogue", "example", "check_question"]:
                if key not in desc or not desc[key]:
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
        warnings.warn("Pathway config validation errors: " + "; ".join(errors), category=UserWarning)

_validate_on_import()

def _detect_subtype(category: str, user_message: str, objection_type: str) -> str:
    pathway_config = _load_pathway_config()
    category_data = pathway_config.get("category_mapping", {}).get(category, {})
    subtypes = category_data.get("subtypes", [])

    msg_lower = user_message.lower()
    best_match = None
    max_matches = 0

    for subtype_info in subtypes:
        subtype_id = subtype_info.get("id", "")
        indicators = subtype_info.get("indicators", [])

        matches = sum(1 for indicator in indicators if indicator.lower() in msg_lower)
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

    objection_type = base_dict.get("type", "unknown")
    category = type_to_category.get(objection_type, "unclear")
    category_data = category_mapping.get(category, {})

    subtype = _detect_subtype(category, user_message, objection_type)

    reframe_descs = {}
    for reframe_id in category_data.get("reframes", []):
        if reframe_id in reframe_descriptions:
            desc_data = reframe_descriptions[reframe_id]
            reframe_descs[reframe_id] = {
                "title": desc_data.get("title", ""),
                "dialogue": desc_data.get("dialogue", ""),
                "example": desc_data.get("example", ""),
                "check_question": desc_data.get("check_question", ""),
            }

    funding_options = []
    if category == "resource":
        funding_options = category_data.get("funding_options", [])

    open_wallet_applicable = category_data.get("open_wallet_applicable", False)

    pathway: ObjectionPathway = {
        **base_dict,
        "category": category,
        "subtype": subtype,
        "entry_question": category_data.get("entry_question", ""),
        "reframes": category_data.get("reframes", []),
        "reframe_descriptions": reframe_descs,
        "funding_options": funding_options,
        "open_wallet_applicable": open_wallet_applicable,
        "dialogue_guidance": category_data.get("dialogue_guidance", ""),
        "is_primary_objection": True,
    }

    return pathway

def analyze_objection_pathway(
    user_message: str,
    history: Optional[list[dict]] = None,
    attempt_count: int = 0,
    conversation_context: Optional[dict] = None,
) -> ObjectionPathway:
    base_dict = classify_objection(user_message, history)
    pathway = _build_pathway_metadata(base_dict, user_message)
    return pathway

def get_reframe_sequence(
    pathway: ObjectionPathway,
    current_turn_in_stage: int,
    history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    reframes = pathway.get("reframes", [])
    reframe_descriptions = pathway.get("reframe_descriptions", {})

    attempts_per_reframe = {reframe_id: 0 for reframe_id in reframes}

    if history:
        for msg in history:
            if msg.get("role") == "assistant":
                content = msg.get("content", "").lower()
                for reframe_id in reframes:
                    marker = f"reframe_{reframe_id}"
                    if marker in content:
                        attempts_per_reframe[reframe_id] += 1

    current_reframe_index = 0
    for i, reframe_id in enumerate(reframes):
        if attempts_per_reframe[reframe_id] == 0:
            current_reframe_index = i
            break
    else:
        current_reframe_index = len(reframes)

    current_reframe = reframes[current_reframe_index] if current_reframe_index < len(reframes) else None
    current_attempts = attempts_per_reframe.get(current_reframe, 0) if current_reframe else 0

    next_check_question = ""
    if current_reframe:
        reframe_desc = reframe_descriptions.get(current_reframe, {})
        next_check_question = reframe_desc.get("check_question", "Does that make sense?")

    return {
        "current_reframe": current_reframe,
        "reframe_index": current_reframe_index,
        "attempts_so_far": current_attempts,
        "next_check_question": next_check_question,
        "is_final_reframe": current_reframe_index >= len(reframes) - 1 if current_reframe else False,
    }


def _get_objection_pathway_safe(
    user_message: str, history: list[dict]
) -> dict[str, Any]:
    """
    Get objection pathway with graceful fallback.
    Tries analyze_objection_pathway first; falls back to classify_objection if it fails.
    """
    try:
        return analyze_objection_pathway(user_message, history)
    except Exception as e:
        _base_logger.debug(f"Pathway analysis failed, falling back: {e}")
        return classify_objection(user_message, history)


def _build_objection_context(
    strategy, stage, user_message, history, objection_data=None
):
    from .analysis import commitment_or_walkaway
    
    stage_value = getattr(stage, "value", stage)
    if str(stage_value).lower() != "objection" or not user_message:
        return ""

    if commitment_or_walkaway(history, user_message, 0):
        return ""

    info = (
        objection_data
        if isinstance(objection_data, dict)
        else classify_objection(user_message, history)
    )
    if info.get("type") == "unknown":
        return ""

    flows = SOP_FLOWS_TRANSACTIONAL if strategy == "transactional" else SOP_FLOWS
    steps = flows.get(info["type"], SOP_FLOW_FALLBACK)

    # Build base context block
    context = (
        f"OBJECTION CLASSIFIED: {info['type'].upper()}\n"
        f"REFRAME STRATEGY: {info['strategy']}\n"
        f"GUIDANCE: {info['guidance']}\n\n"
        f"STEPS:\n{steps}\n"
    )

    # Inject pathway-enhanced info if available
    if info.get("category"):
        context += f"\nBARRIER CATEGORY: {info.get('category').upper()}\n"
        context += f"ENTRY QUESTION: {info.get('entry_question', '')}\n"

        reframes = info.get("reframes", [])
        if reframes:
            reframe_names = ", ".join(reframes)
            context += f"REFRAME SEQUENCE: {reframe_names}\n"
            
            reframe_descs = info.get("reframe_descriptions", {})
            if reframe_descs:
                context += "REFRAME DIALOGUE EXAMPLES:\n"
                for rf_id in reframes:
                    if rf_id in reframe_descs:
                        desc = reframe_descs[rf_id]
                        context += f"- {desc.get('title', rf_id)}:\n"
                        context += f"  Dialogue: {desc.get('dialogue', '').strip()}\n"
                        context += f"  Example: {desc.get('example', '').strip()}\n"
                        context += f"  Check Question: {desc.get('check_question', '').strip()}\n"

        if info.get("category") == "resource":
            context += "\n=== RESOURCE PATHWAY LOGIC ===\n"
            if "dialogue_guidance" in info:
                context += info["dialogue_guidance"].strip() + "\n"
            funding_opts = info.get("funding_options", [])
            if funding_opts:
                funding_str = ", ".join(funding_opts)
                context += f"Available options: {funding_str}\n"

        if info.get("open_wallet_applicable"):
            context += "\n[OPEN WALLET TEST APPLIES: Ascertain if they are truly ready aside from funds]\n"

    return context
