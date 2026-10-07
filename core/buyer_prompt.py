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


def build_product_context(product_type: str) -> str:
    """What the buyer knows about the product: config and custom prospect data.

    The persona's needs, pains and budget are not repeated here; the template has them.
    """
    try:
        products = loader.load_product_config().get("products", {})
        product = products.get(product_type, products.get("default", {}))
        context = product.get("context", "various products and services")
        blocks = [product.get("knowledge", "")]

        # This KB injection only for prospect-mode
        prospect_knowledge = knowledge.get_custom_knowledge_text()
        if prospect_knowledge:
            blocks.append(
                f"Your research notes (you don't know every technical detail):\n{prospect_knowledge}"
            )
        body = "\n\n".join(b for b in blocks if b)
        return f"{context}\n\n{body}" if body else context
    except Exception:
        return "various products and services"


def build_system_prompt(
    template: str,
    *,
    persona: dict,
    readiness: float,
    product_context: str,
    behaviour_rules: str,
) -> str:
    """Fill the buyer's system prompt template with this turn's state."""
    return template.format(
        name=persona.get("name", "Alex"),
        background=persona.get("background", ""),
        personality=persona.get("personality", ""),
        needs_formatted="\n".join(f"  - {n}" for n in persona.get("needs", [])),
        pain_points_formatted="\n".join(f"  - {p}" for p in persona.get("pain_points", [])),
        budget=persona.get("budget", "mid-range"),
        product_knowledge=product_context,
        readiness_description=range_label(readiness, READINESS_THRESHOLDS, READINESS_LABELS),
        behaviour_rules=behaviour_rules,
    )
