"""
AI Response Generation Service
Handles model inference, prompt processing, and response cleaning
"""

import logging
import time
import re
from typing import Optional

# Import model configuration for dynamic model switching
try:
    from config.model_config import get_active_model_config
except ImportError:
    # Fallback if model_config not available
    def get_active_model_config():
        return {"generation_config": {"max_new_tokens": 120, "do_sample": False, "num_beams": 1, "temperature": 0.7, "repetition_penalty": 1.05}}

logger = logging.getLogger("fitness_chatbot")


def generate_ai_response(prompt: str, pipe, tokenizer=None) -> Optional[str]:
    """Generate AI response using the loaded model with comprehensive cleaning
    
    Args:
        prompt: The prompt to send to the model
        pipe: The pipeline object for text generation
        tokenizer: Optional tokenizer if not included in the pipeline
    
    Returns:
        A clean, natural response from persona perspective or None if failed
    """
    try:
        gen_config = get_active_model_config()["generation_config"]
        
        gen_start = time.time()
        response = pipe(
            prompt,
            max_new_tokens=gen_config.get("max_new_tokens", 120),
            do_sample=False,
            temperature=1.0,
            repetition_penalty=1.1,
            return_full_text=False,
            pad_token_id=(pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
            eos_token_id=(pipe.tokenizer.eos_token_id if hasattr(pipe, 'tokenizer') and pipe.tokenizer else None),
        )
        gen_time = time.time() - gen_start
        logger.info(f"⚡ Model inference completed in {gen_time:.2f}s")
        
        generated_text = response[0]['generated_text'].strip()
        character_response = _extract_response(generated_text, prompt)
        character_response = _clean_response(character_response)
        
        if not _validate_response(character_response):
            return None
        
        _log_generation_stats(character_response, gen_time, pipe, tokenizer)
        return character_response

    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return None


def _extract_response(generated_text: str, prompt: str) -> str:
    """Extract the character response from generated text"""
    if "Mary:" in generated_text:
        parts = generated_text.split("Mary:", 1)
        return parts[1].strip() if len(parts) > 1 else generated_text
    elif prompt in generated_text:
        return generated_text.replace(prompt, "").strip()
    return generated_text


def _clean_response(text: str) -> str:
    """Aggressively clean response from formatting artifacts"""
    text = text.strip()
    
    # Remove markdown and template markers
    text = re.sub(r'###.*?###', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\*\*([^*]*)\*\*', r'\1', text)  # **text** → text
    text = re.sub(r'\*\*', '', text)  # Remove standalone **
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # *text* → text
    text = re.sub(r'#{1,6}\s*', '', text)  # Remove headers
    text = re.sub(r'Response Format:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Now respond as.*?:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\*+', '', text)  # Remove remaining asterisks
    
    # Remove persona labels
    text = re.sub(r'\b\w+\s*\(potential customer\):', '', text, flags=re.IGNORECASE)
    text = re.sub(r'potential customer:', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(Mary|Jake|Sarah|David)\s*:', '', text, flags=re.IGNORECASE)
    
    # Clean whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Remove salesperson references
    text = text.replace("Salesperson:", "").strip()
    text = text.replace("I'm a salesperson", "").strip()
    text = text.replace("I am a salesperson", "").strip()
    text = text.replace("my job is to provide information", "").strip()
    text = text.replace("my job is to", "").strip()
    
    # Fix confidence language for personas
    text = re.sub(r"I understand the benefits", "I've heard about the benefits but I'm not sure", text, flags=re.IGNORECASE)
    text = re.sub(r"I know all about", "I've heard about", text, flags=re.IGNORECASE)
    
    # Remove AI language
    text = text.replace("As an AI", "").strip()
    text = text.replace("I'm an AI", "").strip()
    text = text.strip('"\'')
    
    # Handle incomplete sentences
    if text.startswith(("and my job", "and help you")):
        text = ""
    
    return _ensure_complete_sentences(text)


def _ensure_complete_sentences(text: str) -> str:
    """Ensure response contains complete sentences"""
    if len(text) > 300:
        sentences = text.split('. ')
        if len(sentences) > 1:
            complete_response = sentences[0]
            for i in range(1, len(sentences)):
                if len(complete_response + '. ' + sentences[i]) <= 250:
                    complete_response += '. ' + sentences[i]
                else:
                    break
            text = complete_response
            if not text.endswith(('.', '!', '?')):
                text += '.'
    return text


def _validate_response(text: str) -> bool:
    """Validate response quality"""
    if len(text) < 5:
        logger.warning("Response too short (<5 chars)")
        return False
    
    # Check for salesperson contamination
    forbidden_phrases = [
        "i'm a salesperson", "i am a salesperson", "my job is to provide", 
        "my job is to help you", "as a salesperson"
    ]
    if any(phrase in text.lower() for phrase in forbidden_phrases):
        logger.warning("Response contains salesperson language")
        return False
    
    return True


def _log_generation_stats(text: str, gen_time: float, pipe, tokenizer) -> None:
    """Log generation statistics"""
    try:
        tok = (pipe.tokenizer if hasattr(pipe, 'tokenizer') and pipe.tokenizer else tokenizer)
        new_tokens = len(tok.encode(text)) if tok else max(1, len(text) // 4)
    except Exception:
        new_tokens = max(1, len(text) // 4)
    
    tps = new_tokens / gen_time if gen_time > 0 else new_tokens
    logger.info(f"AI generation: {gen_time:.3f}s | ~{new_tokens} tokens | ~{tps:.1f} tok/s")


def post_process_response(response: str) -> str:
    """Light post-processing for responses
    
    Args:
        response: The initial response
    
    Returns:
        Lightly processed response or empty string if invalid
    """
    return response.strip() if response else ""