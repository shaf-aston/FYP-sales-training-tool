"""Load and cache YAML configuration files"""

import copy
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"

# Signal keys that must exist in signals.yaml. Typo here → runtime error.
_REQUIRED_SIGNAL_KEYS = {
    "commitment", "objection", "walking", "low_intent", "high_intent",
    "guardedness_keywords", "demand_directness", "direct_info_requests", "soft_positive",
    "validation_phrases", "emotional_disclosure",
    "user_consultativeSIGNALS", "user_transactionalSIGNALS",
}

@lru_cache(maxsize=16)
def _load_yaml_cached(filename):
    """Load and cache YAML from CONFIG_DIR. Raises FileNotFoundError if missing."""
    filepath = CONFIG_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Config file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(filename):
    """Return a cached YAML snapshot as a deep copy.

    The underlying parse result stays cached, but callers receive their own copy so
    accidental in-place mutations cannot leak across modules.
    """
    return copy.deepcopy(_load_yaml_cached(filename))


@lru_cache(maxsize=1)
def load_signals():
    """Load signals.yaml and verify all required keys exist."""
    signals = load_yaml("signals.yaml")
    if not isinstance(signals.get("guardedness_keywords"), dict):
        raise ValueError("signals.yaml guardedness_keywords must be a mapping")
    missing = _REQUIRED_SIGNAL_KEYS - signals.keys()
    if missing:
        raise ValueError(f"signals.yaml missing: {sorted(missing)}")

    signal_priority = signals.get("signal_priority", [])
    if signal_priority:
        if not isinstance(signal_priority, list):
            raise ValueError("signals.yaml signal_priority must be a list")
        unknown = [key for key in signal_priority if key not in signals]
        if unknown:
            raise ValueError(
                f"signals.yaml signal_priority references unknown keys: {unknown}"
            )
    return signals


@lru_cache(maxsize=1)
def load_analysis_config():
    """Load analysis_config.yaml."""
    return load_yaml("analysis_config.yaml")


def load_objection_flows():
    """Load objection flow definitions exactly as stored in YAML."""
    return load_yaml("objection_flows.yaml")


@lru_cache(maxsize=1)
def load_product_config():
    """Load product_config.yaml."""
    return load_yaml("product_config.yaml")


@lru_cache(maxsize=1)
def load_prospect_config():
    """Load prospect_config.yaml."""
    return load_yaml("prospect_config.yaml")


@lru_cache(maxsize=1)
def load_real_objections():
    """Real-call objection pool, or [] when disabled or not built yet."""
    cfg = load_prospect_config().get("real_objections", {})
    path = CONFIG_DIR / cfg.get("file", "")
    if not cfg.get("enabled") or not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def load_adaptations():
    """Load prompt adaptation templates from YAML."""
    return load_yaml("adaptations.yaml")


def render_template(template_str, **kwargs):
    """Replace {placeholders} in template_str with kwargs, using sensible defaults."""
    defaults = {"preferences": "not yet specified", "user_message": "", "reason": "",
                "advance_note": "", "next_step": "", "elicitation_example": ""}
    merged = {**defaults, **kwargs}

    result = template_str
    for key, value in merged.items():
        result = result.replace("{" + key + "}", str(value))
    return result


def _by_stage(notes, stage):
    """Pick the note for this stage, else the "default" note."""
    return (notes or {}).get(stage, (notes or {}).get("default", ""))


def get_adaptation_template(adaptation_type, strategy=None, stage=None, **kwargs):
    """Render a prompt block from adaptations.yaml. Returns "" when none matches."""
    data = load_adaptations().get(adaptation_type)
    if adaptation_type == "decisive_user":
        kwargs["advance_note"] = _by_stage(data["advance_note"].get(strategy), stage)
    elif adaptation_type == "low_intent_guarded":
        data = data.get(strategy)
        if data:
            kwargs["next_step"] = _by_stage(data.get("next_step"), stage)
    return render_template(data["template"], **kwargs) if data else ""


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
