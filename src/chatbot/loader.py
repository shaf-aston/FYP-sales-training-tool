"""Unified YAML configuration and template loader.

Centralizes loading of all configuration files (signals, analysis, product configs)
and template files (tactics, overrides, adaptations) with caching.
"""

import yaml
import random
from pathlib import Path
from functools import lru_cache


CONFIG_DIR = Path(__file__).parent.parent / "config"

# Required top-level keys in signals.yaml — guards against silent YAML typos
_REQUIRED_SIGNAL_KEYS = {
    "commitment", "objection", "walking", "impatience",
    "low_intent", "high_intent", "guardedness_keywords", "demand_directness",
    "direct_info_requests", "soft_positive", "validation_phrases",
    "transactional_bot_indicators", "consultative_bot_indicators",
    "user_consultative_signals", "user_transactional_signals",
}


# --- Base YAML Loader ---

@lru_cache(maxsize=None)
def load_yaml(filename):
    """Load and cache a YAML file from CONFIG_DIR. Raises on missing file or parse error."""
    filepath = CONFIG_DIR / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# --- Configuration Loaders ---

def load_signals():
    """Load signals.yaml and validate required keys are present."""
    signals = load_yaml("signals.yaml")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing required keys: {sorted(missing)}")
    return signals


def load_analysis_config():
    """Load analysis_config.yaml with caching via load_yaml()."""
    return load_yaml("analysis_config.yaml")


def load_product_config():
    """Load product_config.yaml with caching via load_yaml()."""
    return load_yaml("product_config.yaml")


@lru_cache(maxsize=1)
def _build_alias_map():
    """Pre-compute alias→settings map for O(1) alias lookup."""
    config = load_product_config()
    alias_map = {}
    for settings in config["products"].values():
        for alias in settings.get("aliases", []):
            alias_map[alias] = settings
    return alias_map


def get_product_settings(product_type):
    """Return product config for the given type or alias. Falls back to default."""
    config = load_product_config()
    products = config["products"]
    
    # Direct match in products
    if product_type in products:
        return products[product_type]
    
    # Try alias lookup
    aliased = _build_alias_map().get(product_type)
    if aliased:
        return aliased
    
    # Fallback to default (inside products dict)
    if "default" in products:
        return products["default"]
    
    # If no default exists, raise error
    raise ValueError(f"Product type '{product_type}' not found and no default config available")


# --- Template Loaders ---

def load_tactics():
    """Load tactics.yaml with caching via load_yaml()."""
    return load_yaml("tactics.yaml")


def load_overrides():
    """Load overrides.yaml with caching via load_yaml()."""
    return load_yaml("overrides.yaml")


def load_adaptations():
    """Load adaptations.yaml with caching via load_yaml()."""
    return load_yaml("adaptations.yaml")


# --- Template Utilities ---

def get_tactic(category="elicitation", subtype=None, context=""):
    """Get a random tactic from the specified category/subtype.
    
    Args:
        category: Top-level category (e.g., "elicitation", "lead_ins")
        subtype: Subcategory (e.g., "presumptive", "combined")
        context: Optional context string (reserved for future use)
    
    Returns:
        Random tactic string from the specified category
    """
    tactics = load_tactics()
    
    if category not in tactics:
        return ""
    
    cat_dict = tactics[category]
    
    if subtype and subtype in cat_dict:
        options = cat_dict[subtype]
    elif isinstance(cat_dict, dict):
        # No subtype specified, pick from first available subtype
        first_key = next(iter(cat_dict.keys()))
        options = cat_dict[first_key]
    else:
        options = cat_dict
    
    if not options:
        return ""
    
    return random.choice(options)


def render_template(template_str, **kwargs):
    """Simple template rendering with {keyword} replacement.
    
    Args:
        template_str: Template string with {placeholders}
        **kwargs: Key-value pairs for replacement
    
    Returns:
        Rendered string with placeholders replaced
    """
    # Provide default values for common placeholders
    defaults = {
        "preferences": "not yet specified",
        "user_message": "",
        "reason": "",
        "advance_note": "",
        "elicitation_example": "",
        "base": "",
    }
    
    # Merge defaults with provided kwargs (kwargs take precedence)
    merged = {**defaults, **kwargs}
    
    # Replace placeholders
    result = template_str
    for key, value in merged.items():
        placeholder = "{" + key + "}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    
    return result


def get_override_template(override_type, **kwargs):
    """Get and render an override template.
    
    Args:
        override_type: Type of override ("direct_info_request", "soft_positive_at_pitch", "excessive_validation")
        **kwargs: Template variables for rendering
    
    Returns:
        Rendered override prompt string, or None if override type not found
    """
    overrides = load_overrides()
    
    if override_type not in overrides:
        return None
    
    template = overrides[override_type].get("template", "")
    return render_template(template, **kwargs)


def get_adaptation_template(adaptation_type, strategy=None, **kwargs):
    """Get and render an adaptation template.
    
    Args:
        adaptation_type: Type of adaptation ("decisive_user", "literal_question", "low_intent_guarded")
        strategy: Strategy type ("consultative" or "transactional") for strategy-specific adaptations
        **kwargs: Template variables for rendering
    
    Returns:
        Rendered adaptation guidance string
    """
    adaptations = load_adaptations()
    
    if adaptation_type not in adaptations:
        return ""
    
    adaptation_data = adaptations[adaptation_type]
    
    # Handle decisive_user (needs advance_note lookup)
    if adaptation_type == "decisive_user":
        advance_note = adaptation_data["advance_note"].get(strategy, "")
        kwargs["advance_note"] = advance_note
        template = adaptation_data["template"]
        return render_template(template, **kwargs)
    
    # Handle literal_question (simple template)
    if adaptation_type == "literal_question":
        template = adaptation_data["template"]
        return render_template(template, **kwargs)
    
    # Handle low_intent_guarded (strategy-specific)
    if adaptation_type == "low_intent_guarded":
        if strategy and strategy in adaptation_data:
            template = adaptation_data[strategy]["template"]
            return render_template(template, **kwargs)
    
    return ""
