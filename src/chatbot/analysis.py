"""Natural Language Understanding and conversation analysis utilities.

PURPOSE:
- Analyze user intent, tone, and conversational state
- Detect behavioral signals (impatience, guardedness, question fatigue)
- Extract preferences and goals from conversation history
- Provide context-aware interpretation of user messages

DESIGN PRINCIPLE:
Separation of concerns - this module handles "understanding what the user said"
while flow.py handles "what to do next" and content.py handles "what to say"

ACADEMIC FOUNDATIONS:
- Speech Act Theory (Searle, 1969): Distinguish illocutionary force
- Relevance Theory (Sperber & Wilson, 1995): Context-dependent interpretation
- Goal Priming (Chartrand & Bargh, 1996): Once goal stated, lock high intent
- Conversational Repair Theory (Schegloff, 1992): Detect frustration patterns
- Discourse Representation (Kamp & Reyle, 1993): Maintain context across turns
"""

import re
from functools import lru_cache

# ============================================================================
# CONFIGURATION - Loaded from YAML (analysis_config.yaml)
# ============================================================================

from .config_loader import load_analysis_config

_yaml_config = load_analysis_config()
CONFIG = {
    "MIN_SUBSTANTIVE_WORD_COUNT": _yaml_config["thresholds"]["min_substantive_word_count"],
    "SHORT_MESSAGE_LIMIT": _yaml_config["thresholds"]["short_message_limit"],
    "QUESTION_FATIGUE_THRESHOLD": _yaml_config["thresholds"]["question_fatigue_threshold"],
    "VALIDATION_LOOP_THRESHOLD": _yaml_config["thresholds"]["validation_loop_threshold"],
    "RECENT_HISTORY_WINDOW": _yaml_config["thresholds"]["recent_history_window"],
    "RECENT_TEXT_MESSAGES": _yaml_config["thresholds"]["recent_text_messages"],
}

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


# Backward compatibility alias
matches_any = text_contains_any_keyword


def extract_recent_user_messages(conversation_history, max_messages=None):
    """Extract recent user messages from conversation history.
    
    Args:
        conversation_history: List of {"role": str, "content": str} dicts
        max_messages: Number of recent user messages to extract (default: CONFIG)
        
    Returns:
        str: Combined text of recent user messages (lowercase)
    """
    if max_messages is None:
        max_messages = CONFIG["RECENT_TEXT_MESSAGES"]
    
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

def _has_user_stated_clear_goal(history):
    """Check if user has explicitly stated a goal/problem in recent history.
    
    Academic Basis: Goal Priming (Chartrand & Bargh, 1996)
    Once goal is primed, subsequent low-engagement responses indicate reflection,
    not disinterest. Lock intent to HIGH until contradicted.
    
    Returns:
        bool: True if clear goal/problem detected in recent conversation
    """
    from .config_loader import load_analysis_config
    goal_indicator_keywords = load_analysis_config()["goal_indicators"]
    
    window = CONFIG["RECENT_HISTORY_WINDOW"]
    recent_messages = history[-window:] if history else []
    
    for message in recent_messages:
        if message.get('role') == 'user':
            user_text = message.get('content', '').lower()
            if any(keyword in user_text for keyword in goal_indicator_keywords):
                return True
    
    return False


def analyze_state(history, user_message="", signal_keywords=None):
    """Unified analysis returning {intent, guarded, question_fatigue}.
    
    Single pass over conversation history to extract:
    - intent (high/medium/low) from keyword signals
    - guarded (bool) if response is short + curt (context-aware)
    - question_fatigue (bool) if recent bot questions exceed threshold
    
    Intent Lock
    If user has stated a clear goal, LOCK intent to HIGH regardless of short responses.
    Academic: Recency Bias + Goal Priming (Kahneman & Tversky, 1974; Chartrand & Bargh, 1996)
    
    Context-Aware Guardedness
    'ok' after substantive answer to question = agreement, not guardedness.
    Academic: Relevance Theory (Sperber & Wilson, 1995)
    
    Args:
        history: Conversation history
        user_message: Current user message
        signal_keywords: Signal keywords dict (default: imported from content.py)
        
    Returns:
        dict: {"intent": str, "guarded": bool, "question_fatigue": bool}
    """
    # Import signals only if not provided (allows testing with custom signals)
    if signal_keywords is None:
        from .content import SIGNALS
        signal_keywords = SIGNALS
    
    # INTENT LOCK: Check if goal was stated
    user_stated_clear_goal = _has_user_stated_clear_goal(history)
    
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
        is_short = len(user_message.split()) <= CONFIG["SHORT_MESSAGE_LIMIT"]
        has_guarded_signal = text_contains_any_keyword(user_message.lower(), signal_keywords["guarded"])
        
        if is_short and has_guarded_signal:
            # Check context: was previous bot message a question?
            prev_bot_asked_question = False
            if history and len(history) >= 1:
                prev_message = history[-1].get('content', '')
                prev_bot_asked_question = '?' in prev_message
            
            # Check if user gave substantive previous answer
            user_gave_substantive_answer = False
            if history and len(history) >= 2:
                prev_user_message = history[-2].get('content', '')
                word_count = len(prev_user_message.split())
                user_gave_substantive_answer = word_count >= CONFIG["MIN_SUBSTANTIVE_WORD_COUNT"]
            
            # Agreement pattern: question → substantive answer → "ok"
            # This is NOT guarded; it's agreement
            is_agreement_pattern = prev_bot_asked_question and user_gave_substantive_answer
            
            guarded = not is_agreement_pattern
    
    # Question fatigue detection
    question_fatigue = False
    if history:
        recent_bot_messages = [msg['content'] for msg in history[-4:] if msg['role'] == 'assistant']
        question_count = sum(1 for msg in recent_bot_messages if '?' in msg)
        question_fatigue = question_count >= CONFIG["QUESTION_FATIGUE_THRESHOLD"]
    
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
    
    # Load preference keywords from config
    from .config_loader import load_analysis_config
    config = load_analysis_config()
    pref_config = config.get("preference_keywords", {})
    
    mentioned = set()
    for msg in history:
        if msg["role"] == "user":
            content_lower = msg["content"].lower()
            
            # Check each category
            for category, keywords in pref_config.items():
                if any(keyword in content_lower for keyword in keywords):
                    # Use category name as canonical form
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
        threshold: Max validations allowed (default: CONFIG)
    
    Returns:
        bool: True if excessive validation detected
    """
    if threshold is None:
        threshold = CONFIG["VALIDATION_LOOP_THRESHOLD"]
    
    if not history or len(history) < 4:
        return False
    
    # Load validation phrases from signals config
    from .config_loader import load_signals
    validation_phrases = load_signals().get("validation_phrases", [])
    
    recent_bot = [m["content"].lower() for m in history[-4:] if m["role"] == "assistant"]
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
    
    # Load patterns from config
    from .config_loader import load_analysis_config
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
    # Load demand/frustration keywords from signals config
    from .config_loader import load_signals
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
