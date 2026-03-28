"""Conversation analysis — intent, signals, state detection.

Pure analysis only. Decisions live in flow.py, prompts in content.py.
"""

import re
import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .loader import load_analysis_config, load_signals
from .constants import MAX_USER_KEYWORDS


@dataclass
class ConversationState:
    """Analyzed state of a conversation turn.

    Attributes:
        intent: User intent level ("low", "medium", "high")
        guarded: Whether user is showing defensive/evasive behaviour
        question_fatigue: Whether bot has asked too many questions recently
        decisive: Whether user is ready to make a decision (high intent + not guarded)
    """
    intent: str
    guarded: bool
    question_fatigue: bool
    decisive: bool

    def __getitem__(self, key: str):
        """Backwards-compatible dict-style access for legacy callers/tests."""
        return getattr(self, key)

    def get(self, key: str, default=None):
        """Backwards-compatible dict.get() style access."""
        return getattr(self, key, default)


_yaml_config = load_analysis_config()
_THRESHOLDS = _yaml_config["thresholds"]
_SIGNALS = load_signals()

_NEGATIONS = frozenset({"not", "don't", "doesn't", "no", "never", "can't", "won't"})

_STOP_WORDS = frozenset({
    'i', 'me', 'my', 'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'can', 'may', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
    'it', 'its', 'this', 'that', 'not', 'no', 'yes', 'just', 'so', 'but', 'and',
    'or', 'if', 'then', 'than', 'too', 'very', 'really', 'also', 'like', 'you',
    'your', 'dont', 'im', 'ive', 'some', 'what', 'how', 'about', 'etc', 'want',
    'need', 'get', 'got', 'one', 'know',
})

# Cached guardedness signal sets (loaded once at import)
_AGREEMENT_WORDS = frozenset(_SIGNALS.get("guardedness_keywords", {}).get("agreement_words", []))
_DISMISSAL_WORDS = frozenset(_SIGNALS.get("guardedness_keywords", {}).get("dismissal", []))

_GOAL_VERB_PATTERN = re.compile(r"\b(?:want to|need to|trying to)\s+\w+\s+\w+")

# Guardedness category weights (evasive signals strongest, defensive weakest)
_GUARDEDNESS_WEIGHTS = {
    "evasive": 0.5,
    "sarcasm": 0.35,
    "deflection": 0.2,
    "defensive": 0.1,
}

# --- Core keyword matching ---

@lru_cache(maxsize=256)
def _build_union_pattern(keyword_tuple) -> re.Pattern:
    """Compile keywords into a single alternation regex. Cached by keyword set."""
    parts = [rf'\b{re.escape(k)}\b' for k in keyword_tuple]
    return re.compile('|'.join(parts), re.IGNORECASE)


def text_contains_any_keyword(text, keywords) -> bool:
    """Return True if text contains any non-negated keyword (word-boundary, case-insensitive).

    Iterates all matches so a negated first match doesn't block a valid later one.
    E.g. "don't need X but I want Y" — "need" is negated, "want" is not -> True.
    """
    if not text or not keywords:
        return False
    pattern = _build_union_pattern(tuple(keywords))
    for match in pattern.finditer(text):
        preceding = text[:match.start()].split()
        if not preceding or preceding[-1].lower() not in _NEGATIONS:
            return True
    return False


# --- State analysis ---

def _has_user_stated_clear_goal(history) -> bool:
    """Return True if user stated a clear goal recently (Intent Lock trigger)."""
    if not history:
        return False
    goal_keywords = _yaml_config["goal_indicators"]
    window = _THRESHOLDS["recent_history_window"]
    recent_user_msgs = [
        m.get("content", "").lower()
        for m in history[-window:]
        if m.get("role") == "user"
    ]
    if any(text_contains_any_keyword(msg, goal_keywords) for msg in recent_user_msgs):
        return True

    # Keep broad intent verbs out of config, but still detect goal phrasing in context.
    return any(_GOAL_VERB_PATTERN.search(msg) for msg in recent_user_msgs)


def classify_intent_level(history, user_message="", signal_keywords=None) -> str:
    """Classify current intent level as "low", "medium", or "high".

    Uses the same intent-lock behaviour as analyze_state so all callers share
    one consistent intent model.
    """
    if signal_keywords is None:
        signal_keywords = load_signals()

    if _has_user_stated_clear_goal(history):
        return "high"

    if not (user_message or history):
        return "medium"

    recent_text = (user_message + " " + _extract_recent_user_text(history, 2)).lower()
    if text_contains_any_keyword(recent_text, signal_keywords["low_intent"]):
        return "low"
    if text_contains_any_keyword(recent_text, signal_keywords["high_intent"]):
        return "high"
    return "medium"


def detect_guardedness(user_message: str, history: list[dict[str, str]]) -> float:
    """Simplified guardedness detection using keyword matching.
    
    Returns float 0.0 (not guarded) to 1.0 (very guarded).
    
    Special case: Single-word agreement after substantive answer is NOT guarded.
    """
    if not user_message:
        return 0.0
    
    msg_lower = user_message.lower().strip()
    msg_length = len(user_message.split())

    # PRIORITY CHECK: Agreement pattern detection
    # Pattern: substantive user response → bot question → "ok" = agreement, NOT guarded
    if msg_lower in _AGREEMENT_WORDS and len(history) >= 2:
        recent_msgs = history[-4:]
        has_substantive_user = any(
            m.get('role') == 'user' and len(m.get('content', '').split()) >= 8
            for m in recent_msgs
        )
        has_bot_question = any(
            m.get('role') == 'assistant' and '?' in m.get('content', '')
            for m in recent_msgs
        )
        if has_substantive_user and has_bot_question:
            return 0.0  # Agreement pattern, not guarded

    # Single-word dismissals (not in agreement_words)
    if msg_lower in _DISMISSAL_WORDS:
        return 0.9

    # Agreement with elaboration (NOT guarded)
    # Guard against empty message (whitespace-only after strip)
    split_msg = msg_lower.split()
    if split_msg and split_msg[0] in _AGREEMENT_WORDS and msg_length > 3:
        return 0.1  # Low guardedness for elaborated agreement

    # Weighted scoring using cached guardedness weights
    guardedness_keywords = _SIGNALS.get("guardedness_keywords", {})
    score = 0.0
    for category, weight in _GUARDEDNESS_WEIGHTS.items():
        keywords = guardedness_keywords.get(category, [])
        if text_contains_any_keyword(msg_lower, keywords):
            score += weight
    
    # Context multiplier: Short reply to detailed question
    if history:
        last_bot = next((m.get('content', '') for m in reversed(history) if m.get('role') == 'assistant'), '')
        if len(last_bot.split()) > 50 and msg_length < 8:
            score *= 1.4
    
    return min(score, 1.0)


def analyze_state(
    history: list[dict[str, str]],
    user_message: str = "",
    signal_keywords: dict[str, Any] | None = None,
) -> ConversationState:
    """Return {intent, guarded, question_fatigue, decisive} for the current turn.

    Implements Intent Lock (high intent sticks once stated) and uses simplified
    guardedness detection via detect_guardedness().
    """
    if signal_keywords is None:
        signal_keywords = load_signals()

    assert signal_keywords is not None  # Type narrowing for pyright

    intent = classify_intent_level(history, user_message, signal_keywords=signal_keywords)

    # Guardedness detection (simplified keyword matching)
    guardedness_level = 0.0
    if user_message:
        guardedness_level = detect_guardedness(user_message, history)
    guarded = guardedness_level > 0.4

    # Decisiveness detection
    decisive = False
    if user_message:
        has_commitment = text_contains_any_keyword(
            user_message.lower(), signal_keywords.get("commitment", [])
        )
        has_high_intent = text_contains_any_keyword(
            user_message.lower(), signal_keywords.get("high_intent", [])
        )
        # Decisive if commitment/high-intent signals AND not guarded
        decisive = (has_commitment or has_high_intent) and not guarded

    # Question fatigue
    question_fatigue = False
    if history:
        recent_bot = [m["content"] for m in history[-4:] if m["role"] == "assistant"]
        question_fatigue = sum(1 for msg in recent_bot if "?" in msg) >= _THRESHOLDS["question_fatigue_threshold"]

    return ConversationState(intent=intent, guarded=guarded, question_fatigue=question_fatigue, decisive=decisive)


# --- Preference and keyword extraction ---

def extract_preferences(history) -> str:
    """Return comma-separated preference categories mentioned by the user.

    Categories defined in analysis_config.yaml (preference_keywords).
    """
    if not history:
        return ""
    pref_config = _yaml_config.get("preference_keywords", {})
    mentioned = set()
    for msg in history:
        if msg["role"] == "user":
            text = msg["content"].lower()
            for category, keywords in pref_config.items():
                if text_contains_any_keyword(text, keywords):
                    mentioned.add(category)
    return ", ".join(sorted(mentioned)) if mentioned else ""


def extract_user_keywords(history: list[dict[str, str]], max_keywords: int = MAX_USER_KEYWORDS) -> list[str]:
    """Extract the user's key terms (nouns/descriptors) for lexical entrainment."""
    keywords = []
    for msg in history:
        if msg["role"] == "user":
            for word in msg["content"].lower().split():
                cleaned = word.strip(".,!?;:'\"")
                if cleaned and len(cleaned) > 2 and cleaned not in _STOP_WORDS and cleaned not in keywords:
                    keywords.append(cleaned)
    return keywords[-max_keywords:]


# --- Detection helpers ---

def is_repetitive_validation(history, threshold=None) -> bool:
    """Detect if the bot has been over-validating recently."""
    if threshold is None:
        threshold = _THRESHOLDS["validation_loop_threshold"]
    if not history or len(history) < 4:
        return False
    validation_phrases = _SIGNALS.get("validation_phrases", [])
    recent_bot = [m["content"].lower() for m in history[-10:] if m["role"] == "assistant"]
    count = sum(1 for msg in recent_bot if text_contains_any_keyword(msg, validation_phrases))
    return count >= threshold


def is_literal_question(user_message) -> bool:
    """Return True if the user is genuinely asking for information (not rhetorical)."""
    if not user_message:
        return False
    msg = user_message.lower().strip()
    patterns = _yaml_config.get("question_patterns", {})
    starters = patterns.get("starters", [])
    rhetorical = patterns.get("rhetorical_markers", [])

    is_question = any(msg.startswith(w) for w in starters) or msg.endswith("?")
    is_rhetorical = text_contains_any_keyword(msg, rhetorical)
    return is_question and not is_rhetorical


def commitment_or_walkaway(history: list[dict[str, str]], user_msg: str, turns: int) -> bool:
    """True when user commits or walks away — objection stage exit."""
    # Use internal _SIGNALS loaded at module level
    return (text_contains_any_keyword(user_msg.lower(), _SIGNALS.get("commitment", [])) or
            text_contains_any_keyword(user_msg.lower(), _SIGNALS.get("walking", [])))


def detect_acknowledgment_context(
    user_message: str,
    history: list[dict[str, str]],
    state: ConversationState,
) -> str:
    """Determine if/how acknowledgment is psychologically warranted this turn.

    Returns: "full" | "light" | "none"
      "full"  → User shared vulnerability or emotional content — validate before moving on
      "light" → User is guarded/evasive — brief acknowledgment lowers defences, creates openness
      "none"  → Info request, factual question, or low-engagement filler — acknowledgment here is noise
    """
    if not user_message:
        return "none"

    msg_lower = user_message.lower()

    # Never acknowledge direct info requests — lead with substance
    direct_requests = _SIGNALS.get("direct_info_requests", [])
    if text_contains_any_keyword(msg_lower, direct_requests):
        return "none"

    # Never acknowledge low-engagement filler (e.g. "all good", "just looking")
    low_intent = _SIGNALS.get("low_intent", [])
    if text_contains_any_keyword(msg_lower, low_intent) and len(user_message.split()) < 6:
        return "none"

    # Full acknowledgment: user shared emotional content or vulnerability
    emotional_keywords = _SIGNALS.get("emotional_disclosure", [])
    if text_contains_any_keyword(msg_lower, emotional_keywords):
        return "full"

    # Full acknowledgment: literal question with personal emotional context in history
    # e.g. "so what can I do?" after they shared a struggle
    if history:
        recent_user = [m["content"].lower() for m in history[-4:] if m["role"] == "user"]
        if any(text_contains_any_keyword(m, emotional_keywords) for m in recent_user):
            if is_literal_question(user_message):
                return "light"

    # Light acknowledgment: guarded/evasive — builds comfort and openness
    if state.guarded:
        return "light"

    # Short factual question — skip it
    if is_literal_question(user_message) and len(user_message.split()) < 8:
        return "none"

    return "none"


def user_demands_directness(history, user_message) -> bool:
    """Detect frustration or explicit demands for a straight answer.

    Triggers pitch skip in flow.py when True.
    """
    demand_keywords = _SIGNALS.get("demand_directness", [])
    msg_lower = user_message.lower()

    if text_contains_any_keyword(msg_lower, demand_keywords):
        return True

    if history and len(history) >= 2 and "i said" in msg_lower:
        return True

    return False


# --- Objection classification ---

_REFRAME_DESCRIPTIONS = {
    "money": {
        "isolate_funds": "Isolate the money concern: 'Setting aside the investment for a moment, is this what you want?'",
        "self_solve": "Calculate cost of inaction: 'What's it costing you monthly to NOT solve this?'",
        "plant_credit": "Introduce financing/payment options: 'Most clients use X to spread the cost.'",
        "funding_options": "Explore alternative funding: 'Have you considered using Y to fund this?'",
    },
    "partner": {
        "same_side": "Get on their side: 'Totally understand. What do you think THEY would say about it?'",
        "open_wallet_test": "Test real decision-maker: 'If they said yes, would YOU move forward?'",
        "schedule_followup": "Bring partner in: 'Want to set up a call with them so they can hear it directly?'",
    },
    "fear": {
        "change_of_process": "Reframe risk as process: 'What's the risk of staying where you are?'",
        "island_analogy": "Use future contrast: 'A year from now, what's worse — trying and adjusting, or staying the same?'",
        "identity_reframe": "Connect to identity: 'You said you wanted [goal]. This is how people like you get there.'",
    },
    "logistical": {
        "solve_mechanics": "Remove the barrier: 'What if I handled [logistics]? Would that change things?'",
        "simplify_process": "Simplify: 'It's actually just [N] steps. Here's exactly what happens next.'",
    },
    "think": {
        "drill_to_root": "Find the real concern: 'Totally fair. What specifically would you be weighing up?'",
        "handle_root_type": "Address root concern: Once identified, handle as money/fear/partner type.",
    },
    "smokescreen": {
        "legitimacy_test": "Test if genuine: 'I hear you. Just so I understand — is it the product itself, or something else?'",
    },
}

_OBJECTION_KEYWORDS = {
    "money": ["expensive", "cost", "price", "afford", "budget", "too much",
              "payment", "financing", "cheaper", "discount", "can't afford",
              "pricey", "money", "investment"],
    "partner": ["spouse", "wife", "husband", "partner", "boss", "manager",
                "team", "check with", "talk to", "get approval", "need to ask",
                "run it by"],
    "fear": ["scared", "worried", "risk", "fail", "wrong choice", "regret",
             "what if", "nervous", "uncertain", "guarantee", "proof"],
    "logistical": ["time", "schedule", "busy", "when", "how long", "process",
                   "complicated", "hassle", "setup", "difficult", "steps"],
    "think": ["think about it", "think it over", "need time", "not sure",
              "let me think", "sleep on it", "consider", "mull it over"],
    "smokescreen": ["not interested", "no thanks", "pass", "nah",
                    "not for me", "i'm good", "all set"],
}

def classify_objection(user_message, history=None) -> dict[str, Any]:
    """Classify objection type and return reframe strategy for the LLM prompt."""
    objection_config = _yaml_config.get("objection_handling", {})
    classification_order = objection_config.get(
        "classification_order",
        ["smokescreen", "partner", "money", "fear", "logistical", "think"],
    )

    msg_lower = user_message.lower()
    combined = msg_lower
    if history:
        recent_user = [m["content"].lower() for m in history[-4:] if m["role"] == "user"]
        # Deduplicate: history already contains current message as last user turn
        if recent_user and recent_user[-1] == msg_lower:
            recent_user = recent_user[:-1]
        combined = " ".join(recent_user) + " " + msg_lower

    for obj_type in classification_order:
        keywords = _OBJECTION_KEYWORDS.get(obj_type, [])
        if text_contains_any_keyword(combined, keywords):
            strategies = objection_config.get("reframe_strategies", {}).get(obj_type, [])
            strategy_name = random.choice(strategies) if strategies else "general_reframe"
            guidance = _REFRAME_DESCRIPTIONS.get(obj_type, {}).get(
                strategy_name,
                f"Address the {obj_type} concern directly using the user's stated goals.",
            )
            return {"type": obj_type, "strategy": strategy_name, "guidance": guidance}

    return {
        "type": "unknown",
        "strategy": "general_reframe",
        "guidance": "Acknowledge the concern. Recall the user's stated goal. Ask what specifically is holding them back.",
    }


# --- Web search trigger helpers ---

def should_trigger_web_search(
    stage: str,
    objection_type: str | None,
    user_message: str,
    config: dict,
) -> bool:
    """Return True if web search enrichment should fire this turn.

    Pure function — config injected as a dict so tests need no file I/O.
    Two trigger paths:
      1. User message contains an explicit evidence/proof phrase (any stage).
      2. Objection stage with a trigger-eligible objection type.
    """
    if not config.get("enabled"):
        return False
    msg_lower = user_message.lower()
    if any(phrase in msg_lower for phrase in config.get("trigger_phrases", [])):
        return True
    if stage == "objection" and objection_type in config.get("trigger_objection_types", []):
        return True
    return False


def build_search_query(
    objection_type: str | None,
    product_type: str,
    templates: dict,
) -> str:
    """Build a focused search query from objection type and product context.

    Pure function — templates injected for easy testing.
    Falls back to the "explicit" template when objection_type is unknown/None.
    """
    keyword = product_type or "product"
    template_key = objection_type if objection_type in templates else "explicit"
    template = templates.get(template_key, "{keyword} facts data")
    return template.replace("{keyword}", keyword)


# --- Internal helpers ---

def _extract_recent_user_text(history, max_messages=None) -> str:
    """Combined lowercase text of the N most recent user messages."""
    if max_messages is None:
        max_messages = _THRESHOLDS["recent_text_messages"]
    if not history:
        return ""
    recent = history[-(max_messages * 2):]
    user_msgs = [m["content"].lower() for m in recent if m["role"] == "user"]
    return " ".join(user_msgs[-max_messages:])
