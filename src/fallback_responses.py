"""

This module contains functions for generating AI responses,
handling fallbacks, and post-processing responses for better quality.
"""

import logging
import random
import time
from typing import List, Dict, Optional

# Configure logger
logger = logging.getLogger("fitness_chatbot")

# Fallback responses (kept for compatibility with other modules)
FALLBACK_RESPONSES = [
    "I'm hoping you can help me figure out the best approach for my fitness goals. What would you suggest?",
    "I was just thinking about how to approach this—could you clarify a bit for me?",
    "I'm just trying to explain how I'm feeling so you can guide me.",
    "Sorry, I got distracted for a moment. Could you ask me that again?",
    "I'd really like to understand what would work best for someone like me."
]

# Global toggle (some modules query this)
fallback_responses_enabled = True

def toggle_fallback_responses(enable: bool):
    """Enable or disable fallback responses."""
    global fallback_responses_enabled
    fallback_responses_enabled = enable
    logger.info(f"Fallback responses {'enabled' if enable else 'disabled'}.")

def generate_ai_response(prompt: str, pipe, tokenizer=None) -> str:
    """Generate AI response using the loaded model with minimal filtering
    
    Args:
        prompt: The prompt to send to the model
        pipe: The pipeline object for text generation
        tokenizer: Optional tokenizer if not included in the pipeline
    
    Returns:
        A natural response from Mary's perspective
    """
    try:
        gen_start = time.time()
        # Lower-latency generation: short output, deterministic search
        response = pipe(
            prompt,
            max_new_tokens=64,
            do_sample=False,
            num_beams=1,
            repetition_penalty=1.05,
            return_full_text=False,
            pad_token_id=(pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
            eos_token_id=(pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
        )
        gen_time = time.time() - gen_start
        
        generated_text = response[0]['generated_text'].strip()
        
        # Extract Mary's response (everything after the prompt)
        if "Mary:" in generated_text:
            # Split at Mary: and take the part after it
            parts = generated_text.split("Mary:", 1)
            if len(parts) > 1:
                character_response = parts[1].strip()
            else:
                character_response = generated_text
        elif prompt in generated_text:
            character_response = generated_text.replace(prompt, "").strip()
        else:
            character_response = generated_text
        
        # Basic cleanup only
        character_response = character_response.strip()
        
        # Remove any leading/trailing quotes or artifacts
        character_response = character_response.strip('"\'')
        
        # Stop at first sentence if it's too long
        if len(character_response) > 200:
            sentences = character_response.split('. ')
            character_response = sentences[0] + '.' if sentences else character_response[:200]
        
        # Light validation - just check if we have something reasonable
        if len(character_response) < 5:
            # Do NOT use textual fallbacks here; signal failure to caller
            logger.warning("Generated response too short (<5 chars). Returning None to avoid fallback.")
            return None
        
        # Approximate token count for throughput logging
        try:
            tok = (pipe.tokenizer if hasattr(pipe, 'tokenizer') and pipe.tokenizer else tokenizer)
            new_tokens = len(tok.encode(character_response)) if tok else max(1, len(character_response) // 4)
        except Exception:
            new_tokens = max(1, len(character_response) // 4)
        tps = new_tokens / gen_time if gen_time > 0 else new_tokens
        logger.info(f"AI generation completed in {gen_time:.3f}s | ~{new_tokens} tokens | ~{tps:.1f} tok/s")
        return character_response

    except Exception as e:
        logger.error(f"AI generation error: {e}")
        # Return None to indicate failure - let calling function decide what to do
        return None

def post_process_response(response: str, message_hash: int) -> str:
    """Light post-processing for Mary's response
    
    Args:
        response: The initial response
        message_hash: Not used anymore, kept for compatibility
    
    Returns:
        Lightly processed response
    """
    if not response:
        return get_fallback()
    
    # Just return the response with minimal processing
    return response.strip()

def get_fallback() -> str:
    """Return a random fallback response when AI generation fails
    
    Returns:
        A generic but natural-sounding fallback response for Mary
    """
    return random.choice(FALLBACK_RESPONSES)

def should_use_fallback(config: dict = None) -> bool:
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
    """Get Mary's fallback response
    
    Returns:
        A Mary-appropriate fallback response
    """
    return "I'm sorry, I got a bit confused there. I'm still adjusting to this whole fitness journey. Could you explain that again?"

def handle_error_response(error: Exception = None) -> str:
    """Generate a friendly error response when AI processing fails
    
    Args:
        error: Optional exception that caused the error
    
    Returns:
        A natural error response from Mary's perspective
    """
    if error:
        logger.error(f"Error generating response for Mary: {error}")
    
    return "I'm sorry, I'm having trouble responding right now. Could you try asking again? - Mary"