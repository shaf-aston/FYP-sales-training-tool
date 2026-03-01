"""Natural Language Understanding and conversation analysis utilities.

PURPOSE:
- Analyze user intent, tone, and conversational state
- Detect behavioral signals
- Extract preferences and goals
- Context-aware interpretation

DESIGN PRINCIPLE:
Pure analysis only—no decision making (flow.py) or content generation (content.py).
"""

import re
import random
from functools import lru_cache

# ============================================================================
# CONFIGURATION - Loaded from YAML (analysis_config.yaml)
# ============================================================================

from .config_loader import load_analysis_config, load_signals

_yaml_config = load_analysis_config()
_T = _yaml_config["thresholds"]  # Shorthand for threshold access

# ============================================================================
# KEYWORD UTILITIES
# ============================================================================

@lru_cache(maxsize=256)
def _compile_keyword_pattern(keyword):
    """Compile and cache regex pattern for keyword matching.
    
    Uses LRU cache to avoid recompiling the same patterns repeatedly.
    Significant performance gain for repeated keyword checks.
    
    Args:
        keyword: Keyword to compile pattern for
        
    Returns:
        Compiled regex pattern
    """
    return re.compile(rf'\b{re.escape(keyword)}\b', re.I)


def text_contains_any_keyword(text, keywords):
    """Check if text contains any keyword using word boundaries (case-insensitive).
    
    Uses cached compiled regex patterns for 5-10x performance improvement.
    Word boundaries avoid false positives:
    - "just" matches "just", not "justice"
    - "need" matches "need", not "needle"
    
    Args:
        text: Text to search (case-insensitive)
        keywords: List of keywords to match
        
    Returns:
        bool: True if any keyword found with word boundaries
    """
    if not text:
        return False
    return any(_compile_keyword_pattern(k).search(text) for k in keywords)


def extract_recent_user_messages(conversation_history, max_messages=None):
    """Extract recent user messages from conversation history.
    
    Args:
        conversation_history: List of {"role": str, "content": str} dicts
        max_messages: Number of recent user messages to extract (default: CONFIG)
        
    Returns:
        str: Combined text of recent user messages (lowercase)
    """
    if max_messages is None:
        max_messages = _T["recent_text_messages"]
    
    if not conversation_history:
        return ""
    
    # Extract last N*2 messages (to account for bot messages), then filter to user
    recent_window = conversation_history[-(max_messages * 2):]
    user_messages = [msg['content'].lower() for msg in recent_window if msg['role'] == 'user']
    return ' '.join(user_messages[-max_messages:])


def check_user_intent_keywords(conversation_history, keywords):
    """Check if recent user messages contain intent keywords.
    
    Convenience wrapper around text_contains_any_keyword for history checking.
    
    Args:
        conversation_history: Conversation history list
        keywords: Keywords to search for
        
    Returns:
        bool: True if keywords found in recent user messages
    """
    recent_text = extract_recent_user_messages(conversation_history)
    return text_contains_any_keyword(recent_text, keywords)


# ============================================================================
# INTENT & STATE ANALYSIS
# ============================================================================

def analyze_state(history, user_message="", signal_keywords=None):
    """Unified analysis returning {intent, guarded, question_fatigue}.
    
    Extracts intent, guardedness, and question fatigue in single pass.
    Implements Intent Lock and Agreement vs Guardedness logic.
    
    Args:
        history: Conversation history
        user_message: Current user message
        signal_keywords: Signal keywords dict (default: content.SIGNALS)
        
    Returns:
        dict: Analysis results
    """
    # Import signals only if not provided (allows testing with custom signals)
    if signal_keywords is None:
        from .content import SIGNALS
        signal_keywords = SIGNALS
    
    # INTENT LOCK: Check if goal was stated (inline _has_user_stated_clear_goal logic)
    goal_indicator_keywords = load_analysis_config()["goal_indicators"]
    window = _T["recent_history_window"]
    user_stated_clear_goal = any(
        text_contains_any_keyword(m.get('content', '').lower(), goal_indicator_keywords)
        for m in history[-window:] if m.get('role') == 'user'
    ) if history else False
    
    # Default intent detection
    intent = 'medium'
    if user_message or history:
        recent_text = (user_message + ' ' + extract_recent_user_messages(history, 2)).lower()
        if text_contains_any_keyword(recent_text, signal_keywords["low_intent"]):
            intent = 'low'
        elif text_contains_any_keyword(recent_text, signal_keywords["high_intent"]):
            intent = 'high'
    
    # INTENT LOCK: Override to HIGH if goal was stated (ignore short responses)
    if user_stated_clear_goal:
        intent = 'high'
    
    # Context-aware guardedness detection
    guarded = False
    if user_message:
        is_short = len(user_message.split()) <= _T["short_message_limit"]
        has_guarded_signal = text_contains_any_keyword(user_message.lower(), signal_keywords["guarded"])
        
        if is_short and has_guarded_signal:
            # Check context: was previous bot message a question?
            prev_bot_asked_question = False
            if history and history[-1].get('role') == 'assistant':
                prev_message = history[-1].get('content', '')
                prev_bot_asked_question = '?' in prev_message
            
            # Check if user gave substantive previous answer
            user_gave_substantive_answer = False
            if history and len(history) >= 2:
                prev_user_message = history[-2].get('content', '')
                word_count = len(prev_user_message.split())
                user_gave_substantive_answer = word_count >= _T["min_substantive_word_count"]
            
            # Agreement pattern: question → substantive answer → "ok"
            # This is NOT guarded; it's agreement
            is_agreement_pattern = prev_bot_asked_question and user_gave_substantive_answer
            
            guarded = not is_agreement_pattern
    
    # Question fatigue detection
    question_fatigue = False
    if history:
        recent_bot_messages = [msg['content'] for msg in history[-4:] if msg['role'] == 'assistant']
        question_count = sum(1 for msg in recent_bot_messages if '?' in msg)
        question_fatigue = question_count >= _T["question_fatigue_threshold"]
    
    return {"intent": intent, "guarded": guarded, "question_fatigue": question_fatigue}


# ============================================================================
# PREFERENCE EXTRACTION
# ============================================================================

def extract_preferences(history):
    """Extract user preferences from conversation history.
    
    Maintains discourse representation (Kamp & Reyle, 1993).
    Working memory constraint: Extract once, reuse (Cowan, 2001).
    
    Args:
        history: Conversation history
        
    Returns:
        str: Comma-separated string of mentioned preferences or empty string
    """
    if not history:
        return ""
    
    config = load_analysis_config()
    pref_config = config.get("preference_keywords", {})
    
    mentioned = set()
    for msg in history:
        if msg["role"] == "user":
            content_lower = msg["content"].lower()
            
            # Check each category
            for category, keywords in pref_config.items():
                if text_contains_any_keyword(content_lower, keywords):
                    mentioned.add(category)
    
    return ", ".join(sorted(mentioned)) if mentioned else ""


# ============================================================================
# CONVERSATION PATTERN DETECTION
# ============================================================================

def is_repetitive_validation(history, threshold=None):
    """Detect validation loops (Grice's Maxim of Relevance).
    
    Academic: Cooperative Principle (Grice, 1975) - excessive validation
    violates Maxim of Quantity ("don't say more than needed").
    
    Args:
        history: Conversation history
        threshold: Max validations allowed (default: ANALYSIS_THRESHOLDS)
    
    Returns:
        bool: True if excessive validation detected
    """
    if threshold is None:
        threshold = _T["validation_loop_threshold"]
    
    if not history or len(history) < 4:
        return False
    
    validation_phrases = load_signals().get("validation_phrases", [])
    
    recent_bot = [m["content"].lower() for m in history[-10:] if m["role"] == "assistant"]
    validation_count = sum(
        1 for msg in recent_bot 
        if any(phrase in msg for phrase in validation_phrases)
    )
    
    return validation_count >= threshold


def is_literal_question(user_message):
    """Detect if user is asking for literal information (not rhetorical).
    
    Academic Basis: Speech Act Theory (Searle, 1969)
    Messages ending with ? are REQUESTS FOR INFORMATION.
    Bot must distinguish: literal question vs rhetorical vs reflective.
    
    Args:
        user_message: User's message
        
    Returns:
        bool: True if message is asking for information
    """
    if not user_message:
        return False
    
    msg_lower = user_message.lower().strip()
    
    config = load_analysis_config()
    patterns = config.get("question_patterns", {})
    
    starters = patterns.get("starters", [])
    rhetorical_markers = patterns.get("rhetorical_markers", [])
    
    # Pattern 1: Starts with question word
    starts_with_question = any(
        msg_lower.startswith(word) for word in starters
    )
    
    # Pattern 2: Ends with question mark
    ends_with_question_mark = msg_lower.endswith('?')
    
    # Pattern 3: Rhetorical questions have specific markers OR multiple clauses
    has_rhetorical_marker = any(marker in msg_lower for marker in rhetorical_markers)
    has_multiple_clauses = msg_lower.count(',') > 1
    is_rhetorical = has_rhetorical_marker or has_multiple_clauses
    
    is_question = starts_with_question or ends_with_question_mark
    
    return is_question and not is_rhetorical


def user_demands_directness(history, user_message):
    """Detect if user is frustrated and demanding direct answers.
    
    Academic Basis: Conversational Repair Theory (Schegloff, 1992) +
    Politeness Collapse (Brown & Levinson, 1987)
    
    When user repeats frustration = politeness breaking down.
    Bot must EXIT current strategy immediately.
    
    Args:
        history: Conversation history
        user_message: Current user message
        
    Returns:
        bool: True if user shows frustration signals
    """
    signals = load_signals()
    demand_indicator_keywords = signals.get("demand_directness", [])
    
    msg_lower = user_message.lower()
    
    # Check for explicit demands or frustration
    has_demand = text_contains_any_keyword(msg_lower, demand_indicator_keywords)
    
    # Check for repeated frustration (user clarifying same concern twice)
    if history and len(history) >= 2:
        prev_user_message = history[-2].get('content', '').lower()
        if prev_user_message and 'i said' in msg_lower:
            # User is repeating themselves = frustration
            return True
    
    return has_demand

def extract_user_keywords(history, max_keywords=6):
    """Extract key nouns/terms from user messages for lexical entrainment.

    Academic Basis: Lexical Entrainment (Brennan & Clark, 1996)
    Embedding user's own terms (not full phrases) builds rapport
    and signals active listening.

    Args:
        history: Conversation history
        max_keywords: Maximum keywords to track

    Returns:
        list: User's key terms for embedding in responses
    """
    # Common filler words to exclude
    stop_words = {'i', 'me', 'my', 'a', 'an', 'the', 'is', 'are', 'was',
                  'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does',
                  'did', 'will', 'would', 'could', 'should', 'can', 'may',
                  'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
                  'it', 'its', 'this', 'that', 'not', 'no', 'yes', 'just',
                  'so', 'but', 'and', 'or', 'if', 'then', 'than', 'too',
                  'very', 'really', 'also', 'like', 'you', 'your', 'dont',
                  'im', 'ive', 'some', 'what', 'how', 'about', 'etc', 'want',
                  'need', 'get', 'got', 'one', 'know'}

    keywords = []
    for msg in history:
        if msg["role"] == "user":
            words = msg["content"].lower().split()
            for word in words:
                cleaned = word.strip(".,!?;:'\"")
                if cleaned and len(cleaned) > 2 and cleaned not in stop_words:
                    if cleaned not in keywords:
                        keywords.append(cleaned)

    return keywords[-max_keywords:]


# ============================================================================
# OBJECTION CLASSIFICATION
# ============================================================================

# Objection type keyword patterns for classification
# Maps each objection type to keywords that signal it
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

# Reframe strategy descriptions for LLM guidance
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
    """Classify objection type from user message and suggest reframe strategy.

    Uses the objection_handling configuration from analysis_config.yaml to
    determine the objection type and select an appropriate reframe strategy.

    Academic Basis: Objection handling frameworks (Cialdini, 2006; Rackham, 1988)
    Classification priority follows the order in analysis_config.yaml to check
    smokescreens first (most common false objections) before genuine concerns.

    Args:
        user_message: Current user message containing the objection
        history: Conversation history for context

    Returns:
        dict: {
            "type": str (objection type or "unknown"),
            "strategy": str (reframe strategy name),
            "guidance": str (LLM-readable reframe instruction)
        }
    """
    config = load_analysis_config()
    objection_config = config.get("objection_handling", {})
    classification_order = objection_config.get("classification_order",
                                                 ["smokescreen", "partner", "money", "fear", "logistical", "think"])

    msg_lower = user_message.lower()
    combined_text = msg_lower
    if history:
        recent_user = [m["content"].lower() for m in history[-4:] if m["role"] == "user"]
        combined_text = " ".join(recent_user) + " " + msg_lower

    # Check each type in priority order
    for obj_type in classification_order:
        keywords = _OBJECTION_KEYWORDS.get(obj_type, [])
        if text_contains_any_keyword(combined_text, keywords):
            # Get reframe strategies from YAML config
            strategies = objection_config.get("reframe_strategies", {}).get(obj_type, [])
            if strategies:
                strategy_name = random.choice(strategies)
            else:
                strategy_name = "general_reframe"

            # Get human-readable guidance
            guidance = _REFRAME_DESCRIPTIONS.get(obj_type, {}).get(
                strategy_name,
                f"Address the {obj_type} concern directly using the user's stated goals."
            )

            return {
                "type": obj_type,
                "strategy": strategy_name,
                "guidance": guidance,
            }

    return {
        "type": "unknown",
        "strategy": "general_reframe",
        "guidance": "Acknowledge the concern. Recall the user's stated goal. Ask what specifically is holding them back.",
    }