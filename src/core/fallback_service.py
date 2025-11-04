"""
Fallback Response Service
Manages fallback responses and error handling
"""

import logging
import random
from typing import Dict, Optional

logger = logging.getLogger("fitness_chatbot")

# Fallback responses for when AI generation fails
FALLBACK_RESPONSES = [
    "I'm hoping you can help me figure out the best approach for my fitness goals. What would you suggest?",
    "I was just thinking about how to approach this—could you clarify a bit for me?",
    "I'm just trying to explain how I'm feeling so you can guide me.",
    "Sorry, I got distracted for a moment. Could you ask me that again?",
    "I'd really like to understand what would work best for someone like me."
]

# Global toggle for fallback responses
fallback_responses_enabled = True


def toggle_fallback_responses(enable: bool) -> None:
    """Enable or disable fallback responses"""
    global fallback_responses_enabled
    fallback_responses_enabled = enable
    logger.info(f"Fallback responses {'enabled' if enable else 'disabled'}")


def get_fallback() -> str:
    """Return a random fallback response when AI generation fails"""
    return random.choice(FALLBACK_RESPONSES)


def should_use_fallback(config: Optional[Dict] = None) -> bool:
    """Check if fallback responses should be used based on configuration
    
    Args:
        config: Configuration dictionary, if available
    
    Returns:
        True if fallback responses should be used, False otherwise
    """
    if not fallback_responses_enabled:
        return False

    if config is None:
        return True  # Default to using fallbacks if no config provided
    
    return config.get("fallback_responses_enabled", True)


def get_mary_fallback() -> str:
    """Get Mary's specific fallback response"""
    return "I'm sorry, I got a bit confused there. I'm still adjusting to this whole fitness journey. Could you explain that again?"


def handle_error_response(error: Optional[Exception] = None) -> str:
    """Generate a friendly error response when AI processing fails
    
    Args:
        error: Optional exception that caused the error
    
    Returns:
        A natural error response from Mary's perspective
    """
    if error:
        logger.error(f"Error generating response for Mary: {error}")
    
    return "I'm sorry, I'm having trouble responding right now. Could you try asking again? - Mary"


def get_persona_fallback(persona_name: str) -> str:
    """Get persona-specific fallback response
    
    Args:
        persona_name: Name of the persona
        
    Returns:
        Persona-appropriate fallback response
    """
    persona_fallbacks = {
        "Mary": get_mary_fallback(),
        "Jake": "Look, I'm skeptical about this whole thing. Can you break it down for me again?",
        "Sarah": "I'm on a tight budget here. Could you explain that in simpler terms?",
        "David": "I don't have much time. Can you give me the quick version?"
    }
    
    return persona_fallbacks.get(persona_name, get_fallback())