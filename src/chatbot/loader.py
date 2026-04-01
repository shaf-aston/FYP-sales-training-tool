"""Unified YAML configuration and template loader.

Centralizes loading of all configuration files (signals, analysis, product configs)
and template files (tactics, overrides, adaptations) with caching.

Includes QuickMatcher utility for fuzzy product-to-config matching.
Includes A/B variant selection for prompt testing in evaluation studies.
"""

import yaml
import random
import re
import hashlib
from pathlib import Path
from functools import lru_cache
from difflib import SequenceMatcher


CONFIG_DIR = Path(__file__).parent.parent / "config"

# Required top-level keys in signals.yaml — guards against silent YAML typos
_REQUIRED_SIGNAL_KEYS = {
    "commitment", "objection", "walking", "impatience",
    "low_intent", "high_intent", "guardedness_keywords", "demand_directness",
    "direct_info_requests", "soft_positive", "validation_phrases",
    "transactional_bot_indicators", "consultative_bot_indicators",
    "user_consultative_signals", "user_transactional_signals",
}


@lru_cache(maxsize=None)
def load_yaml(filename):
    """Load and cache a YAML file from CONFIG_DIR. Raises on missing file or parse error."""
    filepath = CONFIG_DIR / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_signals():
    """Load signals.yaml and validate required keys are present."""
    signals = load_yaml("signals.yaml")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing required keys: {sorted(missing)}")

    # Backward-compatible alias expected by older tests/callers.
    if "guarded" not in signals:
        guarded = signals.get("guardedness_keywords", {})
        merged = []
        for key in ("sarcasm", "deflection", "defensive", "dismissal", "evasive"):
            merged.extend(guarded.get(key, []))
        signals["guarded"] = merged

    return signals


def load_analysis_config():
    """Load analysis_config.yaml with caching via load_yaml()."""
    return load_yaml("analysis_config.yaml")


def load_product_config():
    """Load product_config.yaml with caching via load_yaml()."""
    return load_yaml("product_config.yaml")


def load_prospect_config():
    """Load prospect_config.yaml with caching via load_yaml()."""
    return load_yaml("prospect_config.yaml")


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


def load_tactics():
    """Load tactics.yaml with caching via load_yaml()."""
    return load_yaml("tactics.yaml")


def load_overrides():
    """Load overrides.yaml with caching via load_yaml()."""
    return load_yaml("overrides.yaml")


def load_adaptations():
    """Load adaptations.yaml with caching via load_yaml()."""
    return load_yaml("adaptations.yaml")


def load_web_search_config():
    """Load web_search_config.yaml with caching via load_yaml()."""
    return load_yaml("web_search_config.yaml")


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


class QuickMatcher:
    """Fuzzy matching utility for rapid text-to-config searches.

    Provides multiple matching strategies:
    1. Exact match (case-insensitive)
    2. Alias lookup (via product_config aliases)
    3. Keyword containment (any keyword in text)
    4. Fuzzy similarity (difflib ratio)
    5. Domain signal detection (signals.yaml keys)

    Use Cases:
    - Product type detection from free-form user input
    - Strategy detection from conversation context
    - Preference category matching
    - Intent classification
    """

    # Similarity threshold for fuzzy matching (0.0 to 1.0)
    FUZZY_THRESHOLD = 0.7

    @staticmethod
    def normalize(text):
        """Normalize text for matching: lowercase, strip, collapse whitespace."""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.lower().strip())

    @classmethod
    def match_product(cls, text):
        """Match free-form text to a product type.

        Args:
            text: User input text mentioning a product

        Returns:
            tuple: (product_key, confidence) or (None, 0.0)

        Example:
            >>> QuickMatcher.match_product("I want to buy a car")
            ('automotive', 0.85)
            >>> QuickMatcher.match_product("luxury vehicle shopping")
            ('luxury_cars', 0.95)
        """
        normalized = cls.normalize(text)
        return cls._match_product_normalized(normalized)

    @classmethod
    @lru_cache(maxsize=128)
    def _match_product_normalized(cls, normalized):
        """Internal cached method that receives pre-normalized text.

        This ensures cache hits for "Cars" and "cars" since both normalize
        to "cars" before cache lookup.

        Args:
            normalized: Already normalized text (lowercase, trimmed, collapsed whitespace)

        Returns:
            tuple: (product_key, confidence) or (None, 0.0)
        """
        if not normalized:
            return (None, 0.0)

        config = load_product_config()
        products = config["products"]

        best_match = None
        best_score = 0.0

        for product_key, settings in products.items():
            if product_key == "default":
                continue

            # Check exact product key match
            if product_key in normalized:
                return (product_key, 1.0)

            # Check aliases
            aliases = settings.get("aliases", [])
            for alias in aliases:
                alias_norm = cls.normalize(alias)
                if alias_norm in normalized:
                    return (product_key, 0.95)
                # Fuzzy match on alias
                ratio = SequenceMatcher(None, alias_norm, normalized).ratio()
                if ratio > best_score and ratio >= cls.FUZZY_THRESHOLD:
                    best_score = ratio
                    best_match = product_key

            # Check context keywords
            context = cls.normalize(settings.get("context", ""))
            context_words = context.split()
            matches = sum(1 for word in context_words if word in normalized)
            if context_words and matches > 0:
                context_score = matches / len(context_words) * 0.8
                if context_score > best_score:
                    best_score = context_score
                    best_match = product_key

        return (best_match, best_score) if best_match else (None, 0.0)

def assign_ab_variant(session_id):
    """Deterministically assign A/B variant based on session_id.

    Uses hash-based determinism: same session_id always gets same variant.
    Enables controlled prompt experiment (NEPQ variant vs generic variant).

    Args:
        session_id: Unique session identifier

    Returns:
        str: "variant_a" or "variant_b" (deterministic based on session_id)

    Example:
        >>> assign_ab_variant("session_123")
        'variant_a'
        >>> assign_ab_variant("session_123")  # Called again with same ID
        'variant_a'  # Same result
        >>> assign_ab_variant("session_124")
        'variant_b'
    """
    if not session_id:
        return "variant_a"  # default if no session_id

    # Hash session_id and mod by 2 to get 0 or 1
    hash_val = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
    variant_index = hash_val % 2

    return "variant_a" if variant_index == 0 else "variant_b"


def get_variant_prompt(base_prompt, variant_type, strategy=None):
    """Get variant-specific version of a prompt template.

    Looks for variants in variants.yaml (future: can extend to other sources).
    If no variants.yaml or variant not found, returns base_prompt unchanged.

    Args:
        base_prompt: Base prompt template string
        variant_type: "variant_a" or "variant_b"
        strategy: Optional strategy context ("consultative", "transactional")

    Returns:
        str: Variant-specific prompt (or base_prompt if variant not found)

    Example:
        >>> get_variant_prompt(base_prompt, "variant_a", strategy="consultative")
        # Returns NEPQ-aligned variant if available
    """
    try:
        variants = load_yaml("variants.yaml")
    except FileNotFoundError:
        # No variants.yaml — use base prompt
        return base_prompt

    if not variants or variant_type not in variants:
        return base_prompt

    variant_data = variants[variant_type]

    if "prompts" in variant_data and isinstance(variant_data["prompts"], dict):
        prompts = variant_data["prompts"]
        if strategy and strategy in prompts:
            return prompts[strategy]
        first_template = next(iter(prompts.values()), None)
        if first_template:
            return first_template

    return base_prompt
