"""Conversation analysis — intent, signals, state detection.

Pure analysis only. Decisions live in flow.py, prompts in content.py.
"""

import re
import random
from functools import lru_cache

from .config_loader import load_analysis_config, load_signals

_yaml_config = load_analysis_config()
_T = _yaml_config["thresholds"]

_NEGATIONS = frozenset({"not", "don't", "doesn't", "no", "never", "can't", "won't"})


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

def analyze_state(history, user_message="", signal_keywords=None):
    """Return {intent, guarded, question_fatigue, decisive} for the current turn.

    Implements Intent Lock (high intent sticks once stated) and distinguishes
    agreement ("ok" after substantive answer) from guardedness ("ok" to a question).
    """
    if signal_keywords is None:
        from .content import SIGNALS
        signal_keywords = SIGNALS

    # Intent Lock: check if goal was stated in recent history
    goal_keywords = _yaml_config["goal_indicators"]
    window = _T["recent_history_window"]
    user_stated_goal = any(
        text_contains_any_keyword(m.get("content", "").lower(), goal_keywords)
        for m in history[-window:] if m.get("role") == "user"
    ) if history else False

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

    # Guardedness / decisiveness detection
    guarded = False
    decisive = False
    if user_message:
        is_short = len(user_message.split()) <= _T["short_message_limit"]

        if is_short:
            has_commitment = text_contains_any_keyword(
                user_message.lower(), signal_keywords.get("commitment", [])
            )
            has_high_intent = text_contains_any_keyword(
                user_message.lower(), signal_keywords.get("high_intent", [])
            )

            if has_commitment or has_high_intent:
                decisive = True
            else:
                has_guarded = text_contains_any_keyword(
                    user_message.lower(), signal_keywords["guarded"]
                )
                if has_guarded:
                    prev_bot_asked = (
                        history and history[-1].get("role") == "assistant"
                        and "?" in history[-1].get("content", "")
                    )
                    prev_user_substantive = (
                        len(history) >= 2
                        and len(history[-2].get("content", "").split()) >= _T["min_substantive_word_count"]
                    )
                    # Agreement pattern: question -> substantive answer -> "ok" is NOT guarded
                    guarded = not (prev_bot_asked and prev_user_substantive)

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
    stop_words = {
        'i', 'me', 'my', 'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'can', 'may', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'it', 'its', 'this', 'that', 'not', 'no', 'yes', 'just', 'so', 'but', 'and',
        'or', 'if', 'then', 'than', 'too', 'very', 'really', 'also', 'like', 'you',
        'your', 'dont', 'im', 'ive', 'some', 'what', 'how', 'about', 'etc', 'want',
        'need', 'get', 'got', 'one', 'know',
    }
    keywords = []
    for msg in history:
        if msg["role"] == "user":
            for word in msg["content"].lower().split():
                cleaned = word.strip(".,!?;:'\"")
                if cleaned and len(cleaned) > 2 and cleaned not in stop_words and cleaned not in keywords:
                    keywords.append(cleaned)
    return keywords[-max_keywords:]


# --- Detection helpers ---

def is_repetitive_validation(history, threshold=None):
    """Detect if the bot has been over-validating recently."""
    if threshold is None:
        threshold = _T["validation_loop_threshold"]
    if not history or len(history) < 4:
        return False
    validation_phrases = load_signals().get("validation_phrases", [])
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
    is_rhetorical = any(m in msg for m in rhetorical) or msg.count(",") > 1
    return is_question and not is_rhetorical


def user_demands_directness(history, user_message):
    """Detect frustration or explicit demands for a straight answer.

    Triggers pitch skip in flow.py when True.
    """
    signals = load_signals()
    demand_keywords = signals.get("demand_directness", [])
    msg_lower = user_message.lower()

    if text_contains_any_keyword(msg_lower, demand_keywords):
        return True

    if history and len(history) >= 2 and "i said" in msg_lower:
        return True

    return False


# --- Objection classification ---

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
