"""Custom knowledge base - user-provided product knowledge.

PURPOSE: Allow users to input custom product data (pricing, specs, company info)
that gets injected into the chatbot's prompts alongside built-in product knowledge.

DESIGN PRINCIPLES:
- Separate from config_loader (config = immutable app config; knowledge = mutable user data)
- Graceful degradation: empty/missing knowledge = chatbot works exactly as before
- Simple YAML storage (no database needed for single-user academic project)
- No imports from other chatbot modules (no circular dependencies)
"""

import re
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Only these keys are accepted from the frontend form
ALLOWED_FIELDS = {
    "product_name", "pricing", "specifications",
    "company_info", "selling_points", "additional_notes",
}
MAX_FIELD_LENGTH = 1000

KNOWLEDGE_FILE = Path(__file__).parent.parent / "config" / "custom_knowledge.yaml"


def load_custom_knowledge() -> dict:
    """Load custom knowledge from YAML file.

    Returns:
        dict: Knowledge data, or empty dict if file doesn't exist/is empty
    """
    if not KNOWLEDGE_FILE.exists():
        return {}
    try:
        with open(KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, IOError) as e:
        logger.warning(f"Failed to load custom knowledge: {e}")
        return {}


def _clean_value(value: str) -> str:
    """Normalize user input: collapse whitespace, enforce length cap."""
    value = value.strip()
    value = re.sub(r'[ \t]+', ' ', value)          # collapse spaces/tabs (preserve newlines)
    value = re.sub(r'\n{3,}', '\n\n', value)       # cap consecutive blank lines
    return value[:MAX_FIELD_LENGTH]


def _sanitize_knowledge(data: dict) -> dict:
    """Whitelist fields and clean values before storage."""
    cleaned = {}
    for key, value in data.items():
        if key not in ALLOWED_FIELDS:
            continue
        if isinstance(value, str):
            v = _clean_value(value)
            if v:
                cleaned[key] = v
    return cleaned


def save_custom_knowledge(data: dict) -> bool:
    """Save custom knowledge to YAML file.

    Applies field whitelist and value sanitization before writing.

    Args:
        data: Knowledge dictionary to save

    Returns:
        bool: True if save successful
    """
    try:
        sanitized = _sanitize_knowledge(data)
        KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(sanitized, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except (IOError, yaml.YAMLError) as e:
        logger.error(f"Failed to save custom knowledge: {e}")
        return False


def get_custom_knowledge_text() -> str:
    """Get formatted knowledge text for prompt injection.

    Returns formatted text ready for insertion into product_context.
    Returns empty string if no custom knowledge exists.

    Returns:
        str: Formatted knowledge text or empty string
    """
    data = load_custom_knowledge()
    if not data:
        return ""

    sections = []
    for key, value in data.items():
        if isinstance(value, str) and value.strip():
            sections.append(f"{key}: {value.strip()}")
        elif isinstance(value, list):
            items = "\n".join(f"  - {item}" for item in value if item)
            if items:
                sections.append(f"{key}:\n{items}")

    return "\n".join(sections) if sections else ""


def clear_custom_knowledge() -> bool:
    """Delete all custom knowledge.

    Returns:
        bool: True if deletion successful or file didn't exist
    """
    try:
        if KNOWLEDGE_FILE.exists():
            KNOWLEDGE_FILE.unlink()
        return True
    except IOError as e:
        logger.error(f"Failed to delete custom knowledge: {e}")
        return False
