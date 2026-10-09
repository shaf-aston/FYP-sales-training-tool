"""Builds what the buyer's AI is told: who they are, what they know, how keen they are."""

from . import knowledge, loader  # module refs, so tests can swap the functions
from .buyer_state import persona_name
from .utils import range_label


def build_product_context(product_type: str) -> str:
    """What the buyer knows about the product: config and custom knowledge.

    The persona's needs, pains and budget are not repeated here; the template has them.
    """
    products = loader.load_buyer_products()["products"]
    product = products.get(product_type, products["default"])
    blocks = [product.get("knowledge", "")]
    custom_knowledge = knowledge.get_custom_knowledge_text()
    if custom_knowledge:
        blocks.append(f"{loader.load_buyer_config()['research_notes_heading']}\n{custom_knowledge}")
    body = "\n\n".join(b for b in blocks if b)
    return f"{product['context']}\n\n{body}" if body else product["context"]


def build_system_prompt(
    template: str,
    *,
    persona: dict,
    readiness: float,
    product_context: str,
    behaviour_rules: str,
) -> str:
    """Fill the buyer's system prompt template with this turn's state."""
    bands = loader.load_buyer_config()["readiness_bands"]
    return template.format(
        name=persona_name(persona),
        background=persona.get("background", ""),
        personality=persona.get("personality", ""),
        needs_formatted="\n".join(f"  - {n}" for n in persona.get("needs", [])),
        pain_points_formatted="\n".join(f"  - {p}" for p in persona.get("pain_points", [])),
        budget=persona.get("budget", "mid-range"),
        product_knowledge=product_context,
        readiness_description=range_label(readiness, bands["thresholds"], bands["labels"]),
        behaviour_rules=behaviour_rules,
    )
