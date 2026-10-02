"""Builds what the buyer's AI is told: who they are, what they know, how keen they are."""

from . import knowledge, loader  # module refs, so tests can swap the functions
from .utils import range_label

READINESS_THRESHOLDS = [0.2, 0.4, 0.6, 0.8]
READINESS_LABELS = [
    "Not buying it at all",
    "Still needs convincing",
    "On the fence - some interest but not sold",
    "Getting there, but a few things are holding them back",
    "Almost there - just needs one more good reason",
]


def _persona_context(persona: dict) -> str:
    """The buyer's needs, pains and budget as prompt lines."""
    parts = []
    if persona.get("needs"):
        parts.append("BUYER'S KNOWN NEEDS: " + ", ".join(persona["needs"]))
    if persona.get("pain_points"):
        parts.append("BUYER'S PAIN POINTS: " + ", ".join(persona["pain_points"]))
    if persona.get("budget"):
        parts.append(f"BUYER'S BUDGET: {persona['budget']}")
    return "\n".join(parts)


def build_product_context(product_type: str, persona: dict) -> str:
    """What the buyer knows about the product: config, persona, and custom prospect data."""
    try:
        products = loader.load_product_config().get("products", {})
        product = products.get(product_type, products.get("default", {}))
        context = product.get("context", "various products and services")
        blocks = [product.get("knowledge", ""), _persona_context(persona)]

        # This KB injection only for prospect-mode
        prospect_knowledge = knowledge.get_custom_knowledge_text()
        if prospect_knowledge:
            blocks.append(
                f"--- BEGIN CUSTOM PROSPECT DATA ---\n{prospect_knowledge}\n--- END CUSTOM PROSPECT DATA ---\n"
                "(You may know some of this as buyer research-do not assume full technical knowledge.)"
            )
        body = "\n\n".join(b for b in blocks if b)
        return f"{context}\n\n{body}" if body else context
    except Exception:
        return "various products and services"


def build_system_prompt(
    template: str,
    *,
    persona: dict,
    behaviour: dict,
    readiness: float,
    objections_raised: int,
    turn_count: int,
    product_type: str,
    product_context: str,
    behaviour_rules: str,
) -> str:
    """Fill the buyer's system prompt template with this turn's state."""
    product_knowledge = (
        "PRODUCT INFORMATION (you may know some of this as a buyer doing research):\n"
        f"{product_context}"
        if product_context
        else ""
    )
    return template.format(
        name=persona.get("name", "Alex"),
        background=persona.get("background", ""),
        personality=persona.get("personality", ""),
        needs_formatted="\n".join(f"  - {n}" for n in persona.get("needs", [])),
        pain_points_formatted="\n".join(f"  - {p}" for p in persona.get("pain_points", [])),
        budget=persona.get("budget", "mid-range"),
        product_context=product_type.replace("_", " "),
        product_knowledge=product_knowledge,
        readiness_description=range_label(readiness, READINESS_THRESHOLDS, READINESS_LABELS),
        objections_raised=objections_raised,
        max_objections=behaviour["max_objections"],
        turn_count=turn_count,
        behaviour_rules=behaviour_rules,
    )
