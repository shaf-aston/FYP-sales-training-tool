"""
This module contains functions for generating AI responses,
handling fallbacks, and post-processing responses for better quality.
"""

import logging
import random
import time
from typing import List, Dict, Optional
import re

from config.config_loader import config

logger = logging.getLogger("fitness_chatbot")

FALLBACK_RESPONSES = [
    "I'm hoping you can help me figure out the best approach for my fitness goals. What would you suggest?",
    "I was just thinking about how to approach this—could you clarify a bit for me?",
    "I'm just trying to explain how I'm feeling so you can guide me.",
    "Sorry, I got distracted for a moment. Could you ask me that again?",
    "I'd really like to understand what would work best for someone like me."
]

fallback_responses_enabled = False

def toggle_fallback_responses(enable: bool):
    """Enable or disable fallback responses."""
    global fallback_responses_enabled
    fallback_responses_enabled = enable
    logger.info(f"Fallback responses {'enabled' if enable else 'disabled'}.")

def generate_ai_response(prompt: str, pipe, tokenizer=None) -> str:
    """Generate AI response using the loaded model with minimal filtering"""
    
    try:
        gen_config = {
            "max_new_tokens": config.get("llm.max_tokens", 32),
            "do_sample": True,
            "repetition_penalty": 1.05,
            "num_beams": 1,
            "temperature": config.get("llm.temperature", 0.8)
        }
        
        gen_start = time.time()
        
        generation_params = {
            "max_new_tokens": gen_config["max_new_tokens"],
            "do_sample": gen_config["do_sample"],
            "repetition_penalty": gen_config["repetition_penalty"],
            "num_beams": gen_config["num_beams"],
            "temperature": gen_config["temperature"],
            "return_full_text": False,
            "pad_token_id": (pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
            "eos_token_id": (pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
        }
        
        response = pipe(prompt, **generation_params)
        gen_time = time.time() - gen_start
        
        logger.info(f"AI response generated in {gen_time:.2f}s")
        print(f"AI response generated in {gen_time:.2f}s")
        
        generated_text = response[0]['generated_text'].strip()
        
        if "Mary:" in generated_text:
            parts = generated_text.split("Mary:", 1)
            if len(parts) > 1:
                character_response = parts[1].strip()
            else:
                character_response = generated_text
        elif prompt in generated_text:
            character_response = generated_text.replace(prompt, "").strip()
        else:
            character_response = generated_text
        
        character_response = character_response.strip()
        
        if not prompt.startswith("I'm hoping"):
            character_response = re.sub(r'#|\*\*.*?Format.*?\*\*|Response Format:|Now respond as.*?:', '', character_response, flags=re.IGNORECASE)
            character_response = re.sub(r'\b(?:Mary|Jake|Sarah|David)\s*:', '', character_response, flags=re.IGNORECASE)
            character_response = re.sub(r'\b\w+\s*\(potential customer\):|potential customer:', '', character_response, flags=re.IGNORECASE)
            character_response = re.sub(r"I'm a salesperson|I am a salesperson|Salesperson:|Sales person:|my job is to provide information|my job is to", '', character_response, flags=re.IGNORECASE)
            character_response = re.sub(r"I understand the benefits", "I've heard about the benefits but I'm not sure", character_response, flags=re.IGNORECASE)
            character_response = re.sub(r"I know all about", "I've heard about", character_response, flags=re.IGNORECASE)
            character_response = character_response.strip('"\'').replace("As an AI", '').replace("I'm an AI", '').strip()

            if len(character_response) > 200:
                sentences = character_response.split('. ')
                character_response = sentences[0] + '.' if sentences else character_response[:200]

            if any(phrase in character_response.lower() for phrase in [
                "i'm a salesperson", "i am a salesperson", "my job is to provide", 
                "my job is to help you", "as a salesperson"
            ]) or len(character_response) < 5:
                logger.warning("Response contains salesperson language or is too short. Using fallback.")
                return "I'm not quite sure I understand. Could you explain that differently?"
        
        try:
            tok = (pipe.tokenizer if hasattr(pipe, 'tokenizer') and pipe.tokenizer else tokenizer)
            logger.debug(f"DEBUG: tok type: {type(tok)}, tok: {tok}")
            logger.debug(f"DEBUG: character_response type: {type(character_response)}, character_response: {character_response}")
            new_tokens = len(tok.encode(character_response)) if tok else max(1, len(character_response) // 4)
        except Exception:
            new_tokens = max(1, len(character_response) // 4)
        tps = new_tokens / gen_time if gen_time > 0 else new_tokens
        logger.info(f"AI generation completed in {gen_time:.3f}s | ~{new_tokens} tokens | ~{tps:.1f} tok/s")
        
        logger.info(f"Response: {character_response[:50]}{'...' if len(character_response) > 50 else ''}")
        
        return character_response

    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return "I'm sorry, I'm having trouble understanding right now. Could you rephrase that?"

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
    
    return response.strip()

def get_fallback() -> str:
    """Return a simple fallback response when AI generation fails
    
    Returns:
        A generic response to keep the conversation flowing
    """
    logger.warning("Fallback response used - AI generation may not be working")
    return "I'm not quite sure about that. Could you ask me something else?"

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
        return True
    
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