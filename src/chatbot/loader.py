"""Unified YAML configuration and template loader.

Centralizes loading of all configuration files (signals, analysis, product configs)
and template files (tactics, overrides, adaptations) with caching.

Includes QuickMatcher utility for fuzzy/rapid text-to-config matching.
"""

import yaml
import random
import re
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


# --- Quick Matcher Utility ---

@lru_cache(maxsize=1)
def _build_signal_patterns():
    """Pre-compile regex patterns for all signal categories."""
    signals = load_signals()
    compiled = {}
    for category, keywords in signals.items():
        if not isinstance(keywords, list):
            continue
        patterns = []
        for keyword in keywords:
            keyword_norm = re.sub(r'\s+', ' ', keyword.lower().strip())
            if ' ' not in keyword_norm:
                patterns.append((re.compile(rf'\b{re.escape(keyword_norm)}\b'), keyword))
            else:
                patterns.append((None, keyword_norm, keyword))  # Substring match
        compiled[category] = patterns
    return compiled


@lru_cache(maxsize=1)
def _build_preference_patterns():
    """Pre-compile regex patterns for all preference categories."""
    config = load_analysis_config()
    preference_keywords = config.get("preference_keywords", {})
    compiled = {}
    for category, keywords in preference_keywords.items():
        patterns = []
        for keyword in keywords:
            keyword_norm = re.sub(r'\s+', ' ', keyword.lower().strip())
            if ' ' not in keyword_norm:
                patterns.append((re.compile(rf'\b{re.escape(keyword_norm)}\b'), keyword))
            else:
                patterns.append((None, keyword_norm, keyword))  # Substring match
        compiled[category] = patterns
    return compiled


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
    @lru_cache(maxsize=128)
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

    @classmethod
    def match_signals(cls, text, signal_category):
        """Match text against a specific signal category using pre-compiled patterns.

        Args:
            text: User input text to analyze
            signal_category: Key in signals.yaml (e.g., "commitment", "objection")

        Returns:
            list: Matched signal keywords found in text

        Example:
            >>> QuickMatcher.match_signals("let's do it, sign me up", "commitment")
            ["let's do it", "sign me up"]
        """
        normalized = cls.normalize(text)
        if not normalized:
            return []

        all_patterns = _build_signal_patterns()
        patterns = all_patterns.get(signal_category, [])

        matched = []
        for entry in patterns:
            if len(entry) == 2:
                # Pre-compiled regex pattern
                pattern, keyword = entry
                if pattern.search(normalized):
                    matched.append(keyword)
            else:
                # Substring match (multi-word)
                _, keyword_norm, keyword = entry
                if keyword_norm in normalized:
                    matched.append(keyword)

        return matched

    @classmethod
    def detect_preferences(cls, text):
        """Detect preference categories from text using pre-compiled patterns.

        Args:
            text: User input text to analyze

        Returns:
            dict: {category: [matched_keywords]} for detected preferences

        Example:
            >>> QuickMatcher.detect_preferences("I need something affordable and reliable")
            {'budget': ['affordable'], 'reliability': ['reliable']}
        """
        normalized = cls.normalize(text)
        if not normalized:
            return {}

        all_patterns = _build_preference_patterns()
        detected = {}

        for category, patterns in all_patterns.items():
            matched = []
            for entry in patterns:
                if len(entry) == 2:
                    # Pre-compiled regex pattern
                    pattern, keyword = entry
                    if pattern.search(normalized):
                        matched.append(keyword)
                else:
                    # Substring match (multi-word)
                    _, keyword_norm, keyword = entry
                    if keyword_norm in normalized:
                        matched.append(keyword)
            if matched:
                detected[category] = matched

        return detected

    @classmethod
    def score_text_match(cls, text, target, method="fuzzy"):
        """Calculate match score between two strings.

        Args:
            text: Source text to match
            target: Target string to match against
            method: Matching method ("exact", "contains", "fuzzy")

        Returns:
            float: Match score (0.0 to 1.0)

        Example:
            >>> QuickMatcher.score_text_match("luxury cars", "luxury_cars", "fuzzy")
            0.91
        """
        text_norm = cls.normalize(text)
        target_norm = cls.normalize(target)

        if not text_norm or not target_norm:
            return 0.0

        if method == "exact":
            return 1.0 if text_norm == target_norm else 0.0

        if method == "contains":
            if target_norm in text_norm or text_norm in target_norm:
                shorter, longer = sorted([text_norm, target_norm], key=len)
                return len(shorter) / len(longer)
            return 0.0

        # Default: fuzzy matching using SequenceMatcher
        return SequenceMatcher(None, text_norm, target_norm).ratio()

    @classmethod
    def find_best_match(cls, text, candidates, threshold=0.6):
        """Find the best matching candidate from a list.

        Args:
            text: Source text to match
            candidates: List of candidate strings to match against
            threshold: Minimum score to consider a match (default 0.6)

        Returns:
            tuple: (best_candidate, score) or (None, 0.0)

        Example:
            >>> QuickMatcher.find_best_match("car", ["automotive", "jewelry", "insurance"])
            ('automotive', 0.0)  # No direct match
            >>> QuickMatcher.find_best_match("cars and vehicles", ["automotive", "jewelry"])
            (None, 0.0)
        """
        if not candidates:
            return (None, 0.0)

        text_norm = cls.normalize(text)
        best_candidate = None
        best_score = 0.0

        for candidate in candidates:
            score = cls.score_text_match(text_norm, candidate, method="fuzzy")
            if score > best_score and score >= threshold:
                best_score = score
                best_candidate = candidate

        return (best_candidate, best_score)


# Convenience function for quick product matching
def quick_match_product(text):
    """Convenience function for product matching.

    Args:
        text: User input text

    Returns:
        Product settings dict if matched, else default settings
    """
    product_key, confidence = QuickMatcher.match_product(text)
    if product_key and confidence >= 0.6:
        return get_product_settings(product_key)
    return get_product_settings("default")
