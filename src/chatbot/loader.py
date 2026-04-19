"""Load and cache YAML configuration files"""

import hashlib
import random
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

# Signal keys that must exist in signals.yaml. Typo here → runtime error.
_REQUIRED_SIGNAL_KEYS = {
    "commitment", "objection", "walking", "impatience", "low_intent", "high_intent",
    "guardedness_keywords", "demand_directness", "direct_info_requests", "soft_positive",
    "validation_phrases", "transactional_bot_indicators", "consultative_bot_indicators",
    "user_consultativeSIGNALS", "user_transactionalSIGNALS",
}


@lru_cache(maxsize=16)
def load_yaml(filename):
    """Load and cache YAML from CONFIG_DIR. Raises FileNotFoundError if missing."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_signals():
    """Load signals.yaml and verify all required keys exist."""
    signals = load_yaml("signals.yaml")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing: {sorted(missing)}")
    return signals


def load_analysis_config():
    return load_yaml("analysis_config.yaml")


def load_objection_flows():
    return load_yaml("objection_flows.yaml")


def load_product_config():
    return load_yaml("product_config.yaml")


def load_prospect_config():
    return load_yaml("prospect_config.yaml")


def get_product_settings(product_type):
    """Return product config for the given type, alias, or default. Raises ValueError if none found."""
    config = load_product_config()
    products = config["products"]
    
    if product_type in products:
        return products[product_type]
    
    # Check aliases
    for settings in products.values():
        if product_type in settings.get("aliases", []):
            return settings
    
    # Fall back to default
    if "default" in products:
        return products["default"]
    
    raise ValueError(f"Product '{product_type}' not found and no default available")


def load_tactics():
    return load_yaml("tactics.yaml")


def load_overrides():
    return load_yaml("overrides.yaml")


def load_adaptations():
    return load_yaml("adaptations.yaml")


def load_web_search_config():
    return load_yaml("web_search_config.yaml")


def get_tactic(category="elicitation", subtype=None, context=""):
    """Pick a random tactic string from category/subtype. Returns empty string if not found."""
    tactics = load_tactics()
    if category not in tactics:
        return ""
    
    cat_dict = tactics[category]
    if subtype and subtype in cat_dict:
        options = cat_dict[subtype]
    elif isinstance(cat_dict, dict):
        options = cat_dict[next(iter(cat_dict.keys()))]
    else:
        options = cat_dict
    
    return random.choice(options) if options else ""


def render_template(template_str, **kwargs):
    """Replace {placeholders} in template_str with kwargs, using sensible defaults."""
    defaults = {"preferences": "not yet specified", "user_message": "", "reason": "",
                "advance_note": "", "elicitation_example": "", "base": ""}
    merged = {**defaults, **kwargs}
    
    result = template_str
    for key, value in merged.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def get_override_template(override_type, **kwargs):
    """Render an override template, or None if type not found"""
    overrides = load_overrides()

    if override_type not in overrides:
        return None

    template = overrides[override_type].get("template", "")
    return render_template(template, **kwargs)


def get_adaptation_template(adaptation_type, strategy=None, **kwargs):
    """Render an adaptation template for the given type and strategy"""
    adaptations = load_adaptations()

    if adaptation_type not in adaptations:
        return ""

    adaptation_data = adaptations[adaptation_type]

    # decisive_user needs advance_note lookup
    if adaptation_type == "decisive_user":
        advance_note = adaptation_data["advance_note"].get(strategy, "")
        kwargs["advance_note"] = advance_note
        template = adaptation_data["template"]
        return render_template(template, **kwargs)

    # literal_question — simple template
    if adaptation_type == "literal_question":
        template = adaptation_data["template"]
        return render_template(template, **kwargs)

    # low_intent_guarded — strategy-specific
    if adaptation_type == "low_intent_guarded":
        if strategy and strategy in adaptation_data:
            template = adaptation_data[strategy]["template"]
            return render_template(template, **kwargs)

    return ""


class QuickMatcher:
    """Match free-form text to product keys: exact → alias → keywords → fuzzy."""
    FUZZY_THRESHOLD = 0.7
    
    @staticmethod
    def normalise(text):
        """Lowercase, strip, collapse whitespace."""
        return re.sub(r"\s+", " ", text.lower().strip()) if text else ""
    
    @classmethod
    def match_product(cls, text):
        """Match free-form text to product key. Returns (key, confidence) or (None, 0.0)."""
        return cls._match_product_normalised(cls.normalise(text))
    
    @classmethod
    @lru_cache(maxsize=128)
    def _match_product_normalised(cls, normalised):
        """Cached lookup ensures 'Cars' and 'cars' share cache hit."""
        if not normalised:
            return (None, 0.0)
        
        config = load_product_config()
        best_match, best_score = None, 0.0
        
        for product_key, settings in config["products"].items():
            if product_key == "default":
                continue
            
            # Exact key match
            if product_key in normalised:
                return (product_key, 1.0)
            
            # Alias match
            for alias in settings.get("aliases", []):
                alias_norm = cls.normalise(alias)
                if alias_norm in normalised:
                    return (product_key, 0.95)
                ratio = SequenceMatcher(None, alias_norm, normalised).ratio()
                if ratio > best_score and ratio >= cls.FUZZY_THRESHOLD:
                    best_score, best_match = ratio, product_key
            
            # Context keyword match
            context_words = cls.normalise(settings.get("context", "")).split()
            if context_words:
                matches = sum(1 for word in context_words if word in normalised)
                context_score = (matches / len(context_words)) * 0.8
                if context_score > best_score:
                    best_score, best_match = context_score, product_key
        
        return (best_match, best_score) if best_match else (None, 0.0)


def assign_ab_variant(session_id):
    """Deterministic A/B assignment via MD5 hash. Same session_id → same variant always."""
    if not session_id:
        return "variant_a"
    hash_val = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
    return "variant_a" if (hash_val % 2) == 0 else "variant_b"
