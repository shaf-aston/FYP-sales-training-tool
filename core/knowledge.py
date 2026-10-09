"""Manage custom instructions stored in YAML."""

import logging
import re

import yaml

from .constants import MAX_FIELD_LENGTH
from .loader import CONFIG_DIR, load_yaml

logger = logging.getLogger(__name__)

KNOWLEDGE_FILE = CONFIG_DIR / "custom_instructions.yaml"

# Field id -> label in the buyer's prompt. Config is the only copy; a broken file stops start-up.
LABEL_MAP = {str(k): str(v) for k, v in load_yaml("knowledge_fields.yaml")["label_map"].items()}
ALLOWED_FIELDS = set(LABEL_MAP)


def load_custom_knowledge() -> dict:
    """Load custom knowledge from YAML.

    Returns empty dict if missing or invalid
    """
    if not KNOWLEDGE_FILE.exists():
        return {}
    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, IOError) as e:
        logger.warning(f"Failed to load custom knowledge ({KNOWLEDGE_FILE}): {e}")
        return {}


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


def save_custom_knowledge(data: dict) -> bool:
    """Sanitize and save custom knowledge to YAML. Returns True on success."""
    try:
        sanitized = sanitise_knowledge(data)
        KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            yaml.dump(sanitized, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except (IOError, yaml.YAMLError) as e:
        logger.error(f"Failed to save custom knowledge ({KNOWLEDGE_FILE}): {e}")
        return False


def get_custom_knowledge_text() -> str:
    """Return formatted knowledge text for LLM prompt injection. Empty string if none."""
    data = load_custom_knowledge()
    if not data:
        return ""

    sections = []
    for key, value in data.items():
        label = LABEL_MAP.get(key, key)
        if isinstance(value, str) and value.strip():
            sections.append(f"{label}: {value.strip()}")
        elif isinstance(value, list):
            items = "\n".join(f"  - {item}" for item in value if item)
            if items:
                sections.append(f"{label}:\n{items}")

    return "\n".join(sections) if sections else ""


def clear_custom_knowledge() -> bool:
    """Delete custom knowledge file(s). Returns True on success or if already absent."""
    try:
        KNOWLEDGE_FILE.unlink(missing_ok=True)
        return True
    except IOError as e:
        logger.error(f"Failed to delete custom knowledge ({KNOWLEDGE_FILE}): {e}")
        return False
