"""Load and cache YAML configuration files"""

import hashlib
import random
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

# required keys — catch typos in signals.yaml early
_REQUIRED_SIGNAL_KEYS = {
    "commitment",
    "objection",
    "walking",
    "impatience",
    "low_intent",
    "high_intent",
    "guardedness_keywords",
    "demand_directness",
    "direct_info_requests",
    "soft_positive",
    "validation_phrases",
    "transactional_bot_indicators",
    "consultative_bot_indicators",
    "user_consultativeSIGNALS",
    "user_transactionalSIGNALS",
}


@lru_cache(maxsize=16)  # ~11 config files + headroom
def load_yaml(filename):
    """Load and cache a YAML file from CONFIG_DIR"""
    filepath = CONFIG_DIR / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_signals():
    """Load signals.yaml with key validation"""
    signals = load_yaml("signals.yaml")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing required keys: {sorted(missing)}")

    return signals


def load_analysis_config():
    """Load analysis_config.yaml (cached)"""
    return load_yaml("analysis_config.yaml")


def load_objection_flows():
    """Load objection_flows.yaml (cached)"""
    return load_yaml("objection_flows.yaml")


def load_product_config():
    """Load product_config.yaml (cached)"""
    return load_yaml("product_config.yaml")


def load_prospect_config():
    """Load prospect_config.yaml (cached)"""
    return load_yaml("prospect_config.yaml")


@lru_cache(maxsize=1)
def _build_alias_map():
    """Build alias→settings map once for fast lookups."""
    config = load_product_config()
    alias_map = {}
    for settings in config["products"].values():
        for alias in settings.get("aliases", []):
            alias_map[alias] = settings
    return alias_map


def get_product_settings(product_type):
    """Return product config for the given type or alias, falling back to default"""
    config = load_product_config()
    products = config["products"]

    # direct match
    if product_type in products:
        return products[product_type]

    # alias lookup
    aliased = _build_alias_map().get(product_type)
    if aliased:
        return aliased

    # fall back to default
    if "default" in products:
        return products["default"]

    # no default either
    raise ValueError(
        f"Product type '{product_type}' not found and no default config available"
    )


def load_tactics():
    """Load tactics.yaml (cached)"""
    return load_yaml("tactics.yaml")


def load_overrides():
    """Load overrides.yaml (cached)"""
    return load_yaml("overrides.yaml")


def load_adaptations():
    """Load adaptations.yaml (cached)"""
    return load_yaml("adaptations.yaml")


def load_web_search_config():
    """Load web_search_config.yaml (cached)"""
    return load_yaml("web_search_config.yaml")


def get_tactic(category="elicitation", subtype=None, context=""):
    """Pick a random tactic string from the given category/subtype"""
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
    """Replace {placeholders} in template_str with kwargs"""
    # defaults for common placeholders
    defaults = {
        "preferences": "not yet specified",
        "user_message": "",
        "reason": "",
        "advance_note": "",
        "elicitation_example": "",
        "base": "",
    }

    merged = {**defaults, **kwargs}

    result = template_str
    for key, value in merged.items():
        placeholder = "{" + key + "}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))

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
    """Fuzzy text-to-product matching: exact, alias, keyword, then difflib"""

    FUZZY_THRESHOLD = 0.7

    @staticmethod
    def normalize(text):
        """Lowercase, strip, collapse whitespace"""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.lower().strip())

    @classmethod
    def match_product(cls, text):
        """Match free-form text to a product key. Returns (key, confidence) or (None, 0.0)"""
        normalized = cls.normalize(text)
        return cls._match_product_normalized(normalized)

    @classmethod
    @lru_cache(maxsize=128)
    def _match_product_normalized(cls, normalized):
        """Cached inner method. Normalized input ensures "Cars" and "cars" share cache"""
        if not normalized:
            return (None, 0.0)

        config = load_product_config()
        products = config["products"]

        best_match = None
        best_score = 0.0

        for product_key, settings in products.items():
            if product_key == "default":
                continue

            # exact key match
            if product_key in normalized:
                return (product_key, 1.0)

            # aliases
            aliases = settings.get("aliases", [])
            for alias in aliases:
                alias_norm = cls.normalize(alias)
                if alias_norm in normalized:
                    return (product_key, 0.95)
                # fuzzy match
                ratio = SequenceMatcher(None, alias_norm, normalized).ratio()
                if ratio > best_score and ratio >= cls.FUZZY_THRESHOLD:
                    best_score = ratio
                    best_match = product_key

            # context keywords
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
    """Hash-based deterministic A/B assignment. Same session always gets same variant"""
    if not session_id:
        return "variant_a"  # default if no session_id

    # md5 mod 2 → even split
    hash_val = int(hashlib.md5(session_id.encode()).hexdigest(), 16)
    variant_index = hash_val % 2

    return "variant_a" if variant_index == 0 else "variant_b"
