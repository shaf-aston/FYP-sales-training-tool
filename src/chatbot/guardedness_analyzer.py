"""
Guardedness detection with context-aware logic.

Distinguishes between:
- Genuine agreement vs guarded dismissal
- Engaged responses vs defensive posturing
- Sarcasm vs authentic agreement
"""

import logging

logger = logging.getLogger(__name__)


def detect_guardedness(user_message, history_context):
    """
    Analyse guardedness with context awareness.
    
    Args:
        user_message: Current user message
        history_context: List of conversation history dicts with 'role' and 'content' keys
    
    Returns:
        dict: {
            'guarded': bool,
            'level': float (0.0 to 1.0),
            'reason': str,
            'indicators': list[str]
        }
    """
    msg_lower = user_message.lower().strip()
    msg_length = len(user_message.split())
    indicators = []
    
    # PRIORITY CHECK: Agreement pattern detection
    # Pattern: substantive user response → bot question → "ok" = agreement, NOT guarded
    AGREEMENT_WORDS = {'ok', 'sure', 'fine', 'alright'}
    
    if msg_lower in AGREEMENT_WORDS and len(history_context) >= 2:
        # Look at last 4 messages for: substantive user message + bot question
        recent_msgs = history_context[-4:]
        has_substantive_user = any(
            m.get('role') == 'user' and len(m.get('content', '').split()) >= 8
            for m in recent_msgs
        )
        has_bot_question = any(
            m.get('role') == 'assistant' and '?' in m.get('content', '')
            for m in recent_msgs
        )
        
        if has_substantive_user and has_bot_question:
            logger.debug("Guardedness: Agreement pattern detected")
            return {
                'guarded': False,
                'level': 0.0,
                'reason': 'Agreement pattern: substantive answer followed by acknowledgment',
                'indicators': ['Agreement context']
            }
    
    # Single-word dismissals (if not agreement pattern)
    DISMISSAL_WORDS = {'ok', 'sure', 'fine', 'whatever', 'maybe', 'idk', 'dunno'}
    if msg_lower in DISMISSAL_WORDS:
        logger.debug(f"Guardedness: Single-word dismissal detected: '{msg_lower}'")
        return {
            'guarded': True,
            'level': 0.9,
            'reason': 'Single-word dismissal',
            'indicators': [f"Single word: {msg_lower}"]
        }
    
    # Agreement with elaboration (NOT guarded)
    AGREEMENT_STARTERS = ('ok', 'sure', 'fine', 'alright', 'yeah')
    if msg_lower.startswith(AGREEMENT_STARTERS) and msg_length > 3:
        logger.debug("Guardedness: Agreement with elaboration detected")
        return {
            'guarded': False,
            'level': 0.1,
            'reason': 'Agreement with elaboration',
            'indicators': ['Agreement + detail']
        }
    
    # Sarcasm markers
    SARCASM_PATTERNS = [
        'yeah sure', 'oh sure', 'right...', 'whatever you say',
        'if you say so', 'sure thing', 'yeah right', 'oh really'
    ]
    for pattern in SARCASM_PATTERNS:
        if pattern in msg_lower:
            indicators.append(f"Sarcasm: '{pattern}'")
    
    # Deflection phrases
    DEFLECTION_PHRASES = [
        "i don't know", "i'm not sure", "i guess", "maybe",
        "i'll think about it", "we'll see", "let me consider"
    ]
    for phrase in DEFLECTION_PHRASES:
        if phrase in msg_lower:
            indicators.append(f"Deflection: '{phrase}'")
    
    # Defensive statements
    DEFENSIVE_MARKERS = [
        "it's fine", "no problem", "all good", "don't worry",
        "i'm fine", "i don't need", "i'm good"
    ]
    for marker in DEFENSIVE_MARKERS:
        if marker in msg_lower:
            indicators.append(f"Defensive: '{marker}'")
    
    # Context: Short reply to detailed question
    previous_bot_message = _get_last_bot_message(history_context)
    if previous_bot_message:
        bot_msg_length = len(previous_bot_message.split())
        if bot_msg_length > 50 and msg_length < 8:
            indicators.append(f"Dismissively short ({msg_length} words) to detailed question ({bot_msg_length} words)")
    
    # Evasive question responses
    EVASIVE_PHRASES = [
        "why do you ask", "what do you mean", "why does it matter",
        "why do you care", "what's it to you"
    ]
    for phrase in EVASIVE_PHRASES:
        if phrase in msg_lower:
            indicators.append(f"Evasive: '{phrase}'")
    
    # Calculate level based on indicators
    if indicators:
        level = min(0.3 + (len(indicators) * 0.2), 1.0)
        guarded = level > 0.4
        logger.debug(f"Guardedness: {len(indicators)} indicators, level={level:.2f}")
        return {
            'guarded': guarded,
            'level': level,
            'reason': f"{len(indicators)} guardedness indicators detected",
            'indicators': indicators
        }
    
    # Default: Not guarded
    return {
        'guarded': False,
        'level': 0.0,
        'reason': 'Normal engagement',
        'indicators': []
    }


def _get_last_bot_message(history_context):
    """Extract the most recent bot message from history."""
    if not history_context:
        return None
    
    for entry in reversed(history_context):
        if entry.get('role') == 'assistant':
            return entry.get('content', '')
    
    return None


def is_guarded_response(user_message, history_context, threshold=0.4):
    """
    Simple boolean check for guardedness.
    
    Args:
        user_message: Current user message
        history_context: Conversation history
        threshold: Guardedness level threshold (0.0 to 1.0)
    
    Returns:
        bool: True if guarded, False otherwise
    """
    result = detect_guardedness(user_message, history_context)
    return result['level'] >= threshold


def get_guardedness_level(user_message, history_context):
    """
    Get numeric guardedness level (0.0 to 1.0).
    
    Args:
        user_message: Current user message
        history_context: Conversation history
    
    Returns:
        float: Guardedness level from 0.0 (open) to 1.0 (very guarded)
    """
    result = detect_guardedness(user_message, history_context)
    return result['level']
