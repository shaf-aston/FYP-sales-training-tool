"""A learner's own product details for the sell-mode buyer (the knowledge base page): cleaning them, and the block
the buyer is told. Pure: no storage here. A signed-in learner's copy is kept on their account (accounts.library);
otherwise it stays in their browser. Either way it comes with each new sell call (/api/sell/init `knowledge`), so
one learner's details never reach another's buyer.
"""

import re

from core.infra.constants import MAX_FIELD_LENGTH
from core.infra.loader import load_yaml

# Field id -> label in the buyer's prompt. Config is the only copy; a broken file stops start-up.
LABEL_MAP = {str(k): str(v) for k, v in load_yaml("knowledge_fields.yaml")["label_map"].items()}
ALLOWED_FIELDS = set(LABEL_MAP)


def clean_value(value: str) -> str:
    """Collapse whitespace and enforce the length cap."""
    if not isinstance(value, str):
        return ""

    value = "\n".join(line.strip() for line in value.strip().splitlines())
    # Collapse spaces and tabs (preserve newlines)
    value = re.sub(r"[ \t]+", " ", value)
    # Limit consecutive blank lines to 2
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value[:MAX_FIELD_LENGTH]


def sanitise_knowledge(data: dict) -> dict:
    """Whitelist fields and clean values. Returns only valid entries."""
    cleaned = {}
    for key, value in data.items():
        if key not in ALLOWED_FIELDS:
            continue

        if isinstance(value, str):
            v = clean_value(value)
            if v:
                cleaned[key] = v
        elif isinstance(value, list):
            out_list = [clean_value(item) for item in value if isinstance(item, str)]
            if out_list:
                cleaned[key] = [v for v in out_list if v]

    return cleaned


def knowledge_text(data: dict | None) -> str:
    """The details as the buyer's prompt shows them. Empty string if none."""
    data = sanitise_knowledge(data or {})
    sections = []
    for key, value in data.items():
        label = LABEL_MAP.get(key, key)
        if isinstance(value, str) and value.strip():
            sections.append(f"{label}: {value.strip()}")
        elif isinstance(value, list):
            items = "\n".join(f"  - {item}" for item in value if item)
            if items:
                sections.append(f"{label}:\n{items}")
    return "\n".join(sections)
