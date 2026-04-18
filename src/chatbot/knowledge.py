"""Manage custom product knowledge stored in YAML files"""

import logging
import re
from pathlib import Path

import yaml

from .constants import MAX_FIELD_LENGTH

logger = logging.getLogger(__name__)

ALLOWED_FIELDS = {
    "product_name",
    "pricing",
    "specifications",
    "company_info",
    "selling_points",
    "additional_notes",
}

KNOWLEDGE_DIR = Path(__file__).parent.parent / "config"
KNOWLEDGE_FILE = KNOWLEDGE_DIR / "custom_knowledge.yaml"
KNOWLEDGE_CONFIG_FILE = KNOWLEDGE_DIR / "knowledge_sanitization.yaml"

# Defaults used when config file is missing or invalid
DEFAULT_SUSPICIOUS_PATTERNS = [
    "ignore previous",
    "ignore the previous",
    "disregard previous",
    "disregard the previous",
    "override the system",
    "override previous",
    "follow instructions",
    "follow these instructions",
    "system prompt",
    "assistant:",
    "system:",
    "begin custom product data",
    "end custom product data",
]

DEFAULT_LABEL_MAP = {
    "product_name": "Product name",
    "pricing": "Pricing",
    "specifications": "Specifications",
    "company_info": "Company information",
    "selling_points": "Selling points",
    "additional_notes": "Additional notes",
}


def _load_kb_sanitization_config():
    """Load sanitisation config (suspicious patterns + optional label map)."""
    try:
        if KNOWLEDGE_CONFIG_FILE.exists():
            with open(KNOWLEDGE_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            patterns = cfg.get("suspicious_patterns", DEFAULT_SUSPICIOUS_PATTERNS)
            label_map = cfg.get("label_map", DEFAULT_LABEL_MAP)
            # normalize
            patterns = [p.lower() for p in patterns if isinstance(p, str)]
            if not isinstance(label_map, dict):
                label_map = DEFAULT_LABEL_MAP
            label_map = {str(k): str(v) for k, v in label_map.items()}
            return patterns, label_map
    except Exception as e:
        logger.warning(
            "Failed to load KB sanitization config (%s): %s", KNOWLEDGE_CONFIG_FILE, e
        )
    return DEFAULT_SUSPICIOUS_PATTERNS, DEFAULT_LABEL_MAP


SUSPICIOUS_PATTERNS, LABEL_MAP = _load_kb_sanitization_config()


def load_custom_knowledge() -> dict:
    """Load custom knowledge from YAML

    Returns empty dict if missing or invalid
    """
    kf = KNOWLEDGE_FILE
    if not kf.exists():
        return {}
    try:
        with open(kf, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except (yaml.YAMLError, IOError) as e:
        logger.warning(f"Failed to load custom knowledge ({kf}): {e}")
        return {}


def clean_value(value: str) -> str:
    """Normalize user input: collapse whitespace, enforce length cap.

    Also performs conservative filtering of lines that look like prompt-injection
    or instruction hooks (e.g. "ignore previous instructions", fenced code
    blocks, or explicit 'system:' / 'assistant:' markers). This keeps custom
    product data strictly factual and reduces the chance of instruction
    injection into the system prompt.
    """
    if not isinstance(value, str):
        return ""

    # Trim and remove fenced code blocks entirely
    value = value.strip()
    value = re.sub(r"```[\s\S]*?```", "", value)

    # Conservative list of suspicious substrings (lowercased checks)
    # Filter out any full lines that appear to attempt to embed instructions
    kept_lines = []
    for ln in value.splitlines():
        s = ln.strip()
        low = s.lower()
        if any(p in low for p in SUSPICIOUS_PATTERNS):
            logger.warning("Stripping suspicious custom-knowledge line: %s", s)
            continue
        kept_lines.append(s)

    value = "\n".join(kept_lines)

    # collapse spaces/tabs (preserve newlines)
    value = re.sub(r"[ \t]+", " ", value)
    # cap consecutive blank lines
    value = re.sub(r"\n{3,}", "\n\n", value)

    return value[:MAX_FIELD_LENGTH]


def sanitize_knowledge(data: dict) -> dict:
    """Whitelist fields and clean values before storage"""
    cleaned = {}
    for key, value in data.items():
        if key not in ALLOWED_FIELDS:
            continue

        # Accept plain strings
        if isinstance(value, str):
            v = clean_value(value)
            if v:
                cleaned[key] = v
            continue

        # Accept lists of strings (preserve as lists after cleaning)
        if isinstance(value, list):
            out_list = []
            for item in value:
                if not isinstance(item, str):
                    continue
                v = clean_value(item)
                if v:
                    out_list.append(v)
            if out_list:
                cleaned[key] = out_list
            continue

        # All other types are skipped
    return cleaned


def save_custom_knowledge(data: dict) -> bool:
    """Sanitize and save custom knowledge to YAML

    Returns True on success
    """
    kf = KNOWLEDGE_FILE
    try:
        sanitized = sanitize_knowledge(data)
        kf.parent.mkdir(parents=True, exist_ok=True)
        with open(kf, "w", encoding="utf-8") as f:
            yaml.dump(
                sanitized,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )
        return True
    except (IOError, yaml.YAMLError) as e:
        logger.error(f"Failed to save custom knowledge ({kf}): {e}")
        return False


def get_custom_knowledge_text() -> str:
    """Return formatted knowledge text for prompt injection. Empty string if none."""
    data = load_custom_knowledge()
    if not data:
        return ""

    sections = []
    for key, value in data.items():
        label = LABEL_MAP.get(key, key)
        if isinstance(value, str) and value.strip():
            # maintain legacy key line for backwards compatibility tests
            if label != key:
                sections.append(f"{key}: {value.strip()}")
            sections.append(f"{label}: {value.strip()}")
        elif isinstance(value, list):
            items = "\n".join(f"  - {item}" for item in value if item)
            if items:
                # include legacy key block when label differs
                if label != key:
                    sections.append(f"{key}:\n{items}")
                sections.append(f"{label}:\n{items}")

    return "\n".join(sections) if sections else ""


def clear_custom_knowledge() -> bool:
    """Delete custom knowledge file. Returns True on success or if already absent"""
    kf = KNOWLEDGE_FILE
    try:
        if kf.exists():
            kf.unlink()
        return True
    except IOError as e:
        logger.error(f"Failed to delete custom knowledge ({kf}): {e}")
        return False
