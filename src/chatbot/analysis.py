"""Conversation analysis — intent, signals, state detection.

Pure analysis only. Decisions live in flow.py, prompts in content.py.
"""

import re
import random
from functools import lru_cache

from .loader import load_analysis_config, load_signals
from .utils import range_label

_GUARD_THRESHOLDS = [1, 2, 3]
_GUARD_LEVELS = [0.0, 0.3, 0.6, 1.0]

_yaml_config = load_analysis_config()
_T = _yaml_config["thresholds"]
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


# --- Core keyword matching ---

@lru_cache(maxsize=256)
def _build_union_pattern(keyword_tuple):
    """Compile keywords into a single alternation regex. Cached by keyword set."""
    parts = [rf'\b{re.escape(k)}\b' for k in keyword_tuple]
    return re.compile('|'.join(parts), re.IGNORECASE)


def text_contains_any_keyword(text, keywords):
    """Return True if text contains any non-negated keyword (word-boundary, case-insensitive).

    Iterates all matches so a negated first match doesn't block a valid later one.
    E.g. "don't need X but I want Y" — "need" is negated, "want" is not -> True.
    """
    if not text or not keywords:
        return False
    pattern = _build_union_pattern(tuple(keywords))
    for match in pattern.finditer(text):
        preceding = text[:match.start()].split()
        if not (preceding and preceding[-1].lower() in _NEGATIONS):
            return True
    return False


# --- State analysis ---

def _has_user_stated_clear_goal(history):
    """Return True if user stated a clear goal recently (Intent Lock trigger)."""
    if not history:
        return False
    goal_keywords = _yaml_config["goal_indicators"]
    window = _T["recent_history_window"]
    return any(
        text_contains_any_keyword(m.get("content", "").lower(), goal_keywords)
        for m in history[-window:] if m.get("role") == "user"
    )


def detect_guardedness(user_message, history):
    """Simplified guardedness detection using keyword matching.
    
    Returns float 0.0 (not guarded) to 1.0 (very guarded).
    
    Special case: Single-word agreement after substantive answer is NOT guarded.
    """
    if not user_message:
        return 0.0
    
    msg_lower = user_message.lower().strip()
    msg_length = len(user_message.split())
    
    # Load guardedness keywords from signals.yaml
    guardedness = _SIGNALS.get("guardedness_keywords", {})
    agreement_words = set(guardedness.get("agreement_words", []))
    
    # PRIORITY CHECK: Agreement pattern detection
    # Pattern: substantive user response → bot question → "ok" = agreement, NOT guarded
    if msg_lower in agreement_words and len(history) >= 2:
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
    dismissal_words = set(guardedness.get("dismissal", []))
    if msg_lower in dismissal_words:
        return 0.9
    
    # Agreement with elaboration (NOT guarded)
    if msg_lower.split()[0] in agreement_words and msg_length > 3:
        return 0.1  # Low guardedness for elaborated agreement
    
    # Count keyword matches from all guardedness categories
    match_count = 0
    for category in ["sarcasm", "deflection", "defensive", "evasive"]:
        keywords = guardedness.get(category, [])
        if any(phrase in msg_lower for phrase in keywords):
            match_count += 1
    
    # Context: Short reply to detailed question
    if history:
        last_bot = next((m.get('content', '') for m in reversed(history) if m.get('role') == 'assistant'), '')
        if len(last_bot.split()) > 50 and msg_length < 8:
            match_count += 1
    
    # Map match count to guardedness level
    return range_label(match_count, _GUARD_THRESHOLDS, _GUARD_LEVELS)


def analyze_state(history, user_message="", signal_keywords=None):
    """Return {intent, guarded, question_fatigue, decisive} for the current turn.

    Implements Intent Lock (high intent sticks once stated) and uses simplified
    guardedness detection via detect_guardedness().
    """
    if signal_keywords is None:
        signal_keywords = load_signals()

    # Intent Lock: check if goal was stated in recent history
    user_stated_goal = _has_user_stated_clear_goal(history)

    # Default intent detection
    intent = "medium"
    if user_message or history:
        recent_text = (user_message + " " + _extract_recent_user_text(history, 2)).lower()
        if text_contains_any_keyword(recent_text, signal_keywords["low_intent"]):
            intent = "low"
        elif text_contains_any_keyword(recent_text, signal_keywords["high_intent"]):
            intent = "high"

    if user_stated_goal:
        intent = "high"

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
        question_fatigue = sum(1 for msg in recent_bot if "?" in msg) >= _T["question_fatigue_threshold"]

    return {"intent": intent, "guarded": guarded, "question_fatigue": question_fatigue, "decisive": decisive}


# --- Preference and keyword extraction ---

def extract_preferences(history):
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


def extract_user_keywords(history, max_keywords=6):
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

def is_repetitive_validation(history, threshold=None):
    """Detect if the bot has been over-validating recently."""
    if threshold is None:
        threshold = _T["validation_loop_threshold"]
    if not history or len(history) < 4:
        return False
    validation_phrases = _SIGNALS.get("validation_phrases", [])
    recent_bot = [m["content"].lower() for m in history[-10:] if m["role"] == "assistant"]
    count = sum(1 for msg in recent_bot if any(phrase in msg for phrase in validation_phrases))
    return count >= threshold


def is_literal_question(user_message):
    """Return True if the user is genuinely asking for information (not rhetorical)."""
    if not user_message:
        return False
    msg = user_message.lower().strip()
    patterns = _yaml_config.get("question_patterns", {})
    starters = patterns.get("starters", [])
    rhetorical = patterns.get("rhetorical_markers", [])

    is_question = any(msg.startswith(w) for w in starters) or msg.endswith("?")
    is_rhetorical = any(m in msg for m in rhetorical)
    return is_question and not is_rhetorical


def detect_acknowledgment_context(user_message, history, state):
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
    if state.get("guarded"):
        return "light"

    # Short factual question — skip it
    if is_literal_question(user_message) and len(user_message.split()) < 8:
        return "none"

    return "none"


def user_demands_directness(history, user_message):
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

def classify_objection(user_message, history=None):
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


# --- Internal helpers ---

def _extract_recent_user_text(history, max_messages=None):
    """Combined lowercase text of the N most recent user messages."""
    if max_messages is None:
        max_messages = _T["recent_text_messages"]
    if not history:
        return ""
    recent = history[-(max_messages * 2):]
    user_msgs = [m["content"].lower() for m in recent if m["role"] == "user"]
    return " ".join(user_msgs[-max_messages:])
