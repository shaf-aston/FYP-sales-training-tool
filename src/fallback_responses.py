"""

This module contains functions for generating AI responses,
handling fallbacks, and post-processing responses for better quality.
"""

import logging
import random
import time
from typing import List, Dict, Optional

# Import model configuration for dynamic model switching
try:
    from config.model_config import get_active_model_config
except ImportError:
    # Fallback if model_config not available
    def get_active_model_config():
        return {"generation_config": {"max_new_tokens": 32, "do_sample": False, "num_beams": 1, "temperature": 0.7, "repetition_penalty": 1.05}}

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

# Global toggle (some modules query this) - DISABLED TO PREVENT REPEATED RESPONSES
fallback_responses_enabled = False

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
    # Check if pipeline is available
    if pipe is None:
        logger.error("❌ Pipeline not available - model failed to load")
        logger.error("Check server logs for detailed error messages")
        # Return a more user-friendly fallback
        return "I'm having trouble connecting to my AI assistant right now. Let me help you anyway - what questions do you have about your fitness goals?"
    
    try:
        # Use configured generation settings (optimized for speed by default)
        gen_config = get_active_model_config()["generation_config"]
        
        gen_start = time.time()
        
        # Use configured generation settings (only valid parameters)
        generation_params = {
            "max_new_tokens": gen_config.get("max_new_tokens", 32),
            "do_sample": gen_config.get("do_sample", False),
            "repetition_penalty": gen_config.get("repetition_penalty", 1.05),
            "num_beams": gen_config.get("num_beams", 1),
            "return_full_text": False,
            "pad_token_id": (pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
            "eos_token_id": (pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
        }
        
        # Only add temperature if sampling is enabled
        if gen_config.get("do_sample", False):
            generation_params["temperature"] = gen_config.get("temperature", 0.7)
        
        response = pipe(prompt, **generation_params)
        gen_time = time.time() - gen_start
        
        # Minimal logging - only response time
        logger.info(f"⚡ AI response generated in {gen_time:.2f}s")
        
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
        
        # Enhanced cleanup for better prospect responses
        character_response = character_response.strip()
        
        # Remove template markers and formatting instructions (CRITICAL FIX)
        import re
        character_response = re.sub(r'###.*?###', '', character_response, flags=re.IGNORECASE | re.DOTALL)
        character_response = re.sub(r'\*\*.*?Format.*?\*\*', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'Response Format:', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'Now respond as.*?:', '', character_response, flags=re.IGNORECASE)
        
        # Remove persona labels from response text (Mary (potential customer):, etc.)
        character_response = re.sub(r'\b\w+\s*\(potential customer\):', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'potential customer:', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'\bMary\s*:', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'\bJake\s*:', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'\bSarah\s*:', '', character_response, flags=re.IGNORECASE)
        character_response = re.sub(r'\bDavid\s*:', '', character_response, flags=re.IGNORECASE)
        
        # Re-strip after regex cleanup
        character_response = character_response.strip()
        
        # AGGRESSIVE removal of salesperson references (AI should ONLY be prospect)
        character_response = character_response.replace("Salesperson:", "").strip()
        character_response = character_response.replace("Sales person:", "").strip()
        character_response = character_response.replace("I'm a salesperson", "").strip()
        character_response = character_response.replace("I am a salesperson", "").strip()
        character_response = character_response.replace("my job is to provide information", "").strip()
        character_response = character_response.replace("my job is to", "").strip()
        
        # Remove phrases that show confidence about fitness (Mary should be uncertain)
        character_response = re.sub(r"I understand the benefits", "I've heard about the benefits but I'm not sure", character_response, flags=re.IGNORECASE)
        character_response = re.sub(r"I know all about", "I've heard about", character_response, flags=re.IGNORECASE)
        
        # Remove any leading/trailing quotes or artifacts
        character_response = character_response.strip('"\'')
        
        # Remove any AI-like language that breaks character
        character_response = character_response.replace("As an AI", "").strip()
        character_response = character_response.replace("I'm an AI", "").strip()
        
        # Remove incomplete sentences that start with removed content
        if character_response.startswith("and my job") or character_response.startswith("and help you"):
            character_response = ""
        
        # Stop at first sentence if it's too long
        if len(character_response) > 200:
            sentences = character_response.split('. ')
            character_response = sentences[0] + '.' if sentences else character_response[:200]
        
        # Check for salesperson contamination and reject if found
        if any(phrase in character_response.lower() for phrase in [
            "i'm a salesperson", "i am a salesperson", "my job is to provide", 
            "my job is to help you", "as a salesperson"
        ]):
            logger.warning("Response contains salesperson language. Using fallback.")
            return "I'm not quite sure I understand. Could you explain that differently?"
        
        # Light validation - just check if we have something reasonable
        if len(character_response) < 5:
            logger.warning("Generated response too short (<5 chars). Using fallback.")
            return "Could you tell me more about that?"
        
        # Approximate token count for throughput logging
        try:
            tok = (pipe.tokenizer if hasattr(pipe, 'tokenizer') and pipe.tokenizer else tokenizer)
            new_tokens = len(tok.encode(character_response)) if tok else max(1, len(character_response) // 4)
        except Exception:
            new_tokens = max(1, len(character_response) // 4)
        tps = new_tokens / gen_time if gen_time > 0 else new_tokens
        logger.info(f"✅ AI generation completed in {gen_time:.3f}s | ~{new_tokens} tokens | ~{tps:.1f} tok/s")
        
        # Minimal logging - only essential info
        logger.info(f"✅ Response: {character_response[:50]}{'...' if len(character_response) > 50 else ''}")
        
        return character_response

    except Exception as e:
        logger.error(f"AI generation error: {e}")
        # Return error message instead of None
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
    
    # Just return the response with minimal processing
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