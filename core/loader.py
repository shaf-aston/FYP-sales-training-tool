"""Load and cache YAML configuration files"""

import copy
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

_DEFAULT_ANALYSIS_CONFIG = {
    "thresholds": {
        "recent_history_window": 6,
        "question_fatigue_threshold": 2,
        "validation_loop_threshold": 2,
        "recent_text_messages": 2,
    },
    "goal_indicators": [
        "want to",
        "need to",
        "trying to",
        "looking for",
        "interested in",
        "buy",
        "purchase",
    ],
    "advancement": {
        "logical": {
            "doubt_keywords": [
                "struggling", "problem", "issue", "stuck", "difficult",
                "not working", "broken", "failing", "doesn't work", "can't",
                "challenge", "obstacle", "bottleneck", "pain point", "weakness",
                "insufficient", "inadequate", "lacking", "missing", "gap",
                "errors", "bugs", "glitches", "slow", "inefficient",
                "why", "how", "doesn't", "shouldn't", "can't seem",
                "tried", "attempts", "haven't been able", "can't figure out",
            ],
            "max_turns": 10,
        },
        "negotiation": {
            "terms_keywords": [
                "price",
                "pricing",
                "cost",
                "quote",
                "budget",
                "payment",
                "payment plan",
                "monthly",
                "per month",
                "terms",
                "deposit",
                "finance",
            ],
            "max_turns": 8,
        },
        "emotional": {
            "stakes_keywords": [
                "stress", "frustrated", "wasting", "costing", "important",
                "worried", "anxious", "concerned", "afraid", "scared",
                "impact", "consequence", "at stake", "depends on", "critical",
                "urgent", "pressure", "deadline", "time sensitive", "rush",
                "losing money", "wasting time", "losing business", "miss out",
                "affects", "matters", "difference", "significant", "deal breaker",
                "must have", "need", "can't live without", "absolutely necessary",
            ],
            "max_turns": 10,
        },
    },
    "preference_keywords": {
        "budget": ["cheap", "affordable", "budget"],
        "quality": ["quality", "reliable", "premium"],
        "speed": ["fast", "quick", "immediate"],
    },
    "drift_detection": {
        "stages": ["logical", "emotional"],
        "min_message_words": 8,
        "redirect_phrase": {
            "logical": "what is not working in their current approach",
            "emotional": "the impact this problem is having on them",
        },
    },
    "question_patterns": {
        "starters": ["what", "how", "why", "when", "where", "who", "is", "are"],
        "rhetorical_markers": ["right", "isn't it", "don't you think"],
    },
    "objection_handling": {
        "classification_order": [
            "smokescreen",
            "partner",
            "money",
            "fear",
            "logistical",
            "think",
        ],
        "reframe_strategies": {
            "smokescreen": ["general_reframe"],
            "partner": ["general_reframe"],
            "money": ["general_reframe"],
            "fear": ["general_reframe"],
            "logistical": ["general_reframe"],
            "think": ["general_reframe"],
        },
    },
}

_DEFAULT_SIGNALS = {
    "commitment": [
        "ready", "let's go", "interested", "yes", "i'm in", "i'm interested",
        "let's proceed", "let's do this", "i'll take it", "sign me up",
        "that works for me", "sounds great", "i'm ready", "count me in",
        "absolutely", "definitely", "for sure", "i want it", "let's get started",
        "ok", "okay", "sure", "alright", "perfect", "great", "i'm down",
        "let's move forward", "i'm committed", "i agree", "sounds perfect",
        "exactly", "that's right", "i'm sold", "let's make it happen",
    ],
    "objection": [
        "but", "however", "concerned", "worried", "afraid", "skeptical",
        "not sure", "hesitant", "doubt", "question", "unsure", "reluctant",
        "nervous", "anxious", "issue", "problem", "concern", "trouble",
        "difficulty", "challenge", "drawback", "downside", "con",
    ],
    "walking": [
        "not interested", "not for me", "pass", "no thanks", "skip",
        "doesn't work for me", "i'm out", "can't do it", "moving on",
        "let's stop", "i'm done", "not right now", "maybe later", "no",
        "nope", "no way", "forget it", "never", "not happening", "drop it",
        "change my mind", "not going", "won't work", "impossible",
    ],
    "impatience": [
        "hurry", "quickly", "fast", "asap", "right now", "immediately",
        "urgent", "now", "today", "tonight", "this week", "don't have time",
        "time's running out", "tick tock", "come on", "let's go", "speed up",
        "how long", "when", "soon", "rushed", "hurrying",
    ],
    "low_intent": [
        "just browsing", "just looking", "killing time", "wasting time",
        "having fun", "curious", "not sure yet", "maybe later", "window shopping",
        "casual", "no hurry", "not urgent", "whenever", "someday", "eventually",
        "i'll think about it", "no pressure", "just exploring",
    ],
    "high_intent": [
        "need to buy", "looking for", "trying to find", "need to find",
        "trying to", "want to", "interested in", "looking to", "shopping for",
        "considering", "evaluating", "comparing", "evaluating", "need help",
        "searching for", "hunting for", "seeking", "looking to purchase",
        "ready to buy", "in the market", "looking to get", "wanting to",
    ],
    "emotional_disclosure": [
        "frustrated", "stressed", "worried", "concerned", "anxious",
        "overwhelmed", "struggling", "desperate", "upset", "angry",
        "disappointed", "exhausted", "tired", "burnt out", "at wit's end",
        "fed up", "can't take it", "losing sleep", "pressure", "tension",
        "difficult time", "hard time", "tough situation", "pain", "hurt",
    ],
    "guardedness_keywords": {
        "agreement_words": [
            "ok", "okay", "sure", "alright", "yes", "yep", "yeah",
            "sounds good", "that's fine", "works for me", "uh-huh"
        ],
        "dismissal": [
            "fine", "whatever", "nope", "no", "nah", "forget it",
            "doesn't matter", "nevermind", "skip it", "never mind"
        ],
        "evasive": [
            "maybe", "not sure", "possibly", "perhaps", "might",
            "could be", "i guess", "sort of", "kind of", "probably"
        ],
        "sarcasm": [
            "yeah right", "obviously", "sure", "right", "oh yeah",
            "great", "wonderful", "fantastic", "lovely", "perfect"
        ],
        "deflection": [
            "depends", "hard to say", "difficult", "complicated",
            "depends on", "case by case", "varies", "it depends"
        ],
        "defensive": [
            "that's not what i meant", "i already said", "i said before",
            "you don't understand", "that's not fair", "you're wrong",
            "i didn't mean that", "look", "listen"
        ],
    },
    "demand_directness": [
        "get to the point", "just tell me", "bottom line", "cut to the chase",
        "what's the bottom line", "just answer", "straight answer", "be direct",
        "stop beating around", "no sugar coating", "the truth", "honestly",
    ],
    "direct_info_requests": [
        "how much", "price", "cost", "what's the price", "how much does",
        "what do you charge", "pricing", "how much will it cost", "price tag",
        "what's it cost", "rate", "fee", "payment", "how much is it",
    ],
    "soft_positive": [
        "that's nice", "sounds good", "cool", "interesting", "okay",
        "alright", "good point", "fair point", "makes sense", "i see"
    ],
    "validation_phrases": [
        "makes sense", "i understand", "i get it", "i see", "right",
        "understood", "got it", "that's fair", "i hear you", "clearly"
    ],
    "transactional_bot_indicators": ["direct", "quick", "fast", "efficient"],
    "consultative_bot_indicators": ["explore", "understand", "discuss", "dive deeper"],
    "user_consultativeSIGNALS": ["tell me more", "explain", "why", "help me understand"],
    "user_transactionalSIGNALS": ["just show me", "quick answer", "get straight", "what's the price"],
}

_DEFAULT_PRODUCT_CONFIG = {
    "products": {
        "default": {
            "name": "Default Product",
            "aliases": ["generic", "standard"],
            "strategy": "consultative",
            "context": "You are a sales representative helping customers find the right product.",
            "knowledge": "Standard product information and features.",
        }
    }
}

_DEFAULT_PROSPECT_CONFIG = {
    "difficulty_profiles": {
        "easy": {
            "behaviour": {
                "initial_readiness": 0.5,
                "readiness_gain_per_good_turn": 0.12,
                "readiness_loss_per_bad_turn": 0.05,
                "max_objections": 1,
                "patience_turns": 15,
            }
        },
        "medium": {
            "behaviour": {
                "initial_readiness": 0.2,
                "readiness_gain_per_good_turn": 0.08,
                "readiness_loss_per_bad_turn": 0.08,
                "max_objections": 3,
                "patience_turns": 12,
            }
        },
        "hard": {
            "behaviour": {
                "initial_readiness": 0.1,
                "readiness_gain_per_good_turn": 0.06,
                "readiness_loss_per_bad_turn": 0.10,
                "max_objections": 5,
                "patience_turns": 10,
            }
        },
    },
    "behaviour_rules": {
        "easy": "Be friendly, open and reasonably receptive.",
        "medium": "Be cautious and ask practical follow-up questions.",
        "hard": "Be skeptical, brief and harder to convince.",
    },
    "personas": {
        "general": [
            {
                "name": "Alex",
                "background": "Professional considering a purchase",
                "needs": ["value", "quality", "reliability"],
                "budget": "mid-range",
                "pain_points": ["current solution isn't meeting needs"],
                "personality": "Practical and straightforward",
            }
        ]
    },
    "system_prompt_template": (
        "You are {name}, a realistic buyer in a sales roleplay.\n"
        "Background: {background}\n"
        "Personality: {personality}\n"
        "Needs:\n{needs_formatted}\n"
        "Pain points:\n{pain_points_formatted}\n"
        "Budget: {budget}\n"
        "Product area: {product_context}\n"
        "{product_knowledge}\n"
        "Current readiness: {readiness_description}\n"
        "Objections raised so far: {objections_raised}/{max_objections}\n"
        "Turn count: {turn_count}\n"
        "Behaviour rules: {behaviour_rules}\n"
        "Stay in character and reply as the buyer."
    ),
    "evaluation": {
        "criteria": {
            "needs_discovery": {
                "weight": 0.25,
                "description": "Ability to ask discovery questions and uncover customer needs"
            },
            "rapport_building": {
                "weight": 0.20,
                "description": "Ability to build trust and demonstrate empathy"
            },
            "objection_handling": {
                "weight": 0.20,
                "description": "Ability to address prospect concerns and overcome objections"
            },
            "solution_presentation": {
                "weight": 0.20,
                "description": "Ability to present solutions that match customer needs"
            },
            "conversation_flow": {
                "weight": 0.15,
                "description": "Overall conversation clarity and balance"
            },
        }
    },
}


def _deep_merge(base, override):
    """Recursively merge override values into a deep copy of base."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


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
    signals = _deep_merge(_DEFAULT_SIGNALS, load_yaml("signals.yaml"))
    guardedness = signals.get("guardedness_keywords")
    if not isinstance(guardedness, dict):
        signals["guardedness_keywords"] = copy.deepcopy(
            _DEFAULT_SIGNALS["guardedness_keywords"]
        )
        if isinstance(guardedness, list):
            signals["guardedness_keywords"]["defensive"] = guardedness
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
    """Load and merge analysis configuration with safe defaults."""
    return _deep_merge(_DEFAULT_ANALYSIS_CONFIG, load_yaml("analysis_config.yaml"))


def load_objection_flows():
    """Load objection flow definitions exactly as stored in YAML."""
    return load_yaml("objection_flows.yaml")


@lru_cache(maxsize=1)
def load_product_config():
    """Load and merge product configuration with built-in defaults."""
    return _deep_merge(_DEFAULT_PRODUCT_CONFIG, load_yaml("product_config.yaml"))


@lru_cache(maxsize=1)
def load_prospect_config():
    """Load and merge prospect mode configuration with built-in defaults."""
    return _deep_merge(_DEFAULT_PROSPECT_CONFIG, load_yaml("prospect_config.yaml"))


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
    """Load conversation tactic templates from YAML."""
    return load_yaml("tactics.yaml")


def load_adaptations():
    """Load prompt adaptation templates from YAML."""
    return load_yaml("adaptations.yaml")


def get_tactic(category="elicitation", subtype=None, context=""):
    """Pick a random tactic string from category/subtype. Returns empty string if not found."""
    raw_tactics = load_tactics()
    # Unwrap nested 'tactics' key if present (YAML structure: tactics: { elicitation: {...} })
    tactics = raw_tactics.get("tactics", raw_tactics)
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

    # literal_question - simple template
    if adaptation_type == "literal_question":
        template = adaptation_data["template"]
        return render_template(template, **kwargs)

    # low_intent_guarded - strategy-specific
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
