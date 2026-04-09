"""Loads, saves, and clears user-provided knowledge from YAML. Injected into prompts at runtime."""

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

_BASE_KNOWLEDGE_DIR = Path(__file__).parent.parent / "config"
_DEFAULT_KNOWLEDGE_FILE = _BASE_KNOWLEDGE_DIR / "custom_knowledge.yaml"

# keep legacy public name for tests
KNOWLEDGE_FILE = _DEFAULT_KNOWLEDGE_FILE


def load_custom_knowledge() -> dict:
    """Load custom knowledge from YAML.

    Returns empty dict if missing or invalid.
    """
    kf = _DEFAULT_KNOWLEDGE_FILE
    if not kf.exists():
        return {}
    try:
        with open(kf, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, IOError) as e:
        logger.warning(f"Failed to load custom knowledge ({kf}): {e}")
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
    """Sanitize and save custom knowledge to YAML.

    Returns True on success.
    """
    try:
        sanitized = _sanitize_knowledge(data)
        kf = _DEFAULT_KNOWLEDGE_FILE
        kf.parent.mkdir(parents=True, exist_ok=True)
        with open(kf, 'w', encoding='utf-8') as f:
            yaml.dump(sanitized, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except (IOError, yaml.YAMLError) as e:
        logger.error(f"Failed to save custom knowledge ({kf}): {e}")
        return False


def get_custom_knowledge_text() -> str:
    """Return formatted knowledge text for prompt injection.

    Returns empty string if none.
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
    """Delete custom knowledge file. Returns True on success or if already absent."""
    try:
        kf = _DEFAULT_KNOWLEDGE_FILE
        if kf.exists():
            kf.unlink()
        return True
    except IOError as e:
        logger.error(f"Failed to delete custom knowledge ({kf}): {e}")
        return False
