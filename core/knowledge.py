"""Manage custom instructions stored in YAML. Filters out prompt-injection attempts."""

import logging
import re
from pathlib import Path

import yaml

from .constants import MAX_FIELD_LENGTH

logger = logging.getLogger(__name__)

ALLOWED_FIELDS = {"product_name", "pricing", "specifications", "company_info", "selling_points", "additional_notes"}

KNOWLEDGE_DIR = Path(__file__).parent.parent / "config"
KNOWLEDGE_FILE = KNOWLEDGE_DIR / "custom_instructions.yaml"
LEGACY_KNOWLEDGE_FILE = KNOWLEDGE_DIR / "custom_knowledge.yaml"
KNOWLEDGE_CONFIG_FILE = KNOWLEDGE_DIR / "knowledge_sanitisation.yaml"

# Patterns that indicate prompt-injection attempts (e.g., "ignore previous instructions")
DEFAULT_INJECTION_PATTERNS = [
    "ignore previous", "ignore the previous", "disregard previous", "disregard the previous",
    "override the system", "override previous", "follow instructions", "follow these instructions",
    "system prompt", "assistant:", "system:", "begin custom product data", "end custom product data",
]

DEFAULT_LABEL_MAP = {
    "product_name": "Product name", "pricing": "Pricing", "specifications": "Specifications",
    "company_info": "Company information", "selling_points": "Selling points",
    "additional_notes": "Additional notes",
}


def _load_kb_sanitisation_config():
    """Load injection-pattern list and label map from config. Falls back to defaults."""
    try:
        if KNOWLEDGE_CONFIG_FILE.exists():
            cfg = yaml.safe_load(open(KNOWLEDGE_CONFIG_FILE, "r", encoding="utf-8")) or {}
            patterns = [p.lower() for p in cfg.get("injection_patterns", DEFAULT_INJECTION_PATTERNS) if isinstance(p, str)]
            label_map = {str(k): str(v) for k, v in (cfg.get("label_map", DEFAULT_LABEL_MAP) or {}).items()}
            return patterns, label_map
    except Exception as e:
        logger.warning("Failed to load KB sanitisation config (%s): %s", KNOWLEDGE_CONFIG_FILE, e)
    return DEFAULT_INJECTION_PATTERNS, DEFAULT_LABEL_MAP


INJECTION_PATTERNS, LABEL_MAP = _load_kb_sanitisation_config()


def load_custom_knowledge() -> dict:
    """Load custom knowledge from YAML.

    Returns empty dict if missing or invalid
    """
    for kf in (KNOWLEDGE_FILE, LEGACY_KNOWLEDGE_FILE):
        if not kf.exists():
            continue
        try:
            with open(kf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except (yaml.YAMLError, IOError) as e:
            logger.warning(f"Failed to load custom knowledge ({kf}): {e}")
            return {}
    return {}


def clean_value(value: str) -> str:
    """Strip code blocks, filter injection-attempt lines, collapse whitespace, enforce length cap."""
    if not isinstance(value, str):
        return ""

    value = value.strip()
    # Remove all fenced code blocks (```...```)
    value = re.sub(r"```[\s\S]*?```", "", value)

    # Filter out lines containing injection patterns (e.g., "ignore previous instructions")
    kept_lines = []
    for line in value.splitlines():
        s = line.strip()
        if not any(pattern in s.lower() for pattern in INJECTION_PATTERNS):
            kept_lines.append(s)
        else:
            logger.warning("Filtered injection attempt: %s", s)

    value = "\n".join(kept_lines)
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
            sections.append(f"{key}: {value.strip()}")
            if label != key:
                sections.append(f"{label}: {value.strip()}")
        elif isinstance(value, list):
            items = "\\n".join(f"  - {item}" for item in value if item)
            if items:
                sections.append(f"{key}:\\n{items}")
                if label != key:
                    sections.append(f"{label}:\\n{items}")

    return "\n".join(sections) if sections else ""


def clear_custom_knowledge() -> bool:
    """Delete custom knowledge file(s). Returns True on success or if already absent."""
    try:
        for path in (KNOWLEDGE_FILE, LEGACY_KNOWLEDGE_FILE):
            if path.exists():
                path.unlink()
        return True
    except IOError as e:
        logger.error(f"Failed to delete custom knowledge ({KNOWLEDGE_FILE}): {e}")
        return False
