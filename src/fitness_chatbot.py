from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
import torch
import uvicorn
import os
import logging
import sys
import time
import hashlib
import json
import re
from pathlib import Path
from typing import List, Dict

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    import codecs
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Add utils to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
from env import setup_model_env, assert_model_present
from paths import LOGS_DIR, MODEL_CACHE_DIR, TEMPLATES_DIR, STATIC_DIR

# Configure logging with UTF-8 encoding for emojis
log_handlers = [
    logging.FileHandler(LOGS_DIR / "chatbot.log", encoding='utf-8'),
]

# Only add console handler if we can handle UTF-8
try:
    import codecs
    if sys.platform == "win32":
        # Try to set UTF-8 encoding for Windows console
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    log_handlers.append(logging.StreamHandler())
except:
    # Skip console logging if UTF-8 not supported
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)
logger = logging.getLogger("fitness_chatbot")

# Optimization flags - optimized for CPU performance
ENABLE_4BIT = os.environ.get("ENABLE_4BIT", "0") == "1"  # Disabled by default for CPU
ENABLE_ACCELERATE = os.environ.get("ENABLE_ACCELERATE", "0") == "1"  # Disabled by default
ENABLE_OPTIMUM = os.environ.get("ENABLE_OPTIMUM", "1") == "1"  # Keep this enabled

def _load_pipeline(model_name: str):
    """Load model with progressive optimization attempts - CPU optimized."""
    start_time = time.time()
    logger.info("🚀 Starting FAST model loading process...")
    
    # Set torch to use all CPU cores
    import torch
    torch.set_num_threads(torch.get_num_threads())  # Use all available cores
    
    # Tokenizer loading timing
    tokenizer_start = time.time()
    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        cache_dir=MODEL_CACHE_DIR,
        trust_remote_code=True
    )
    tokenizer_time = time.time() - tokenizer_start
    logger.info(f"⏱️ Tokenizer loaded in {tokenizer_time:.2f} seconds")

    model_kwargs = dict(
        cache_dir=MODEL_CACHE_DIR,
        trust_remote_code=True,
        pretrained_model_name_or_path=model_name,
        torch_dtype=torch.float32,  # Use float32 for CPU (faster than float16 on CPU)
        low_cpu_mem_usage=True      # Optimize CPU memory usage
    )

    loaded_with = "standard"

    # Try bitsandbytes 4-bit
    if ENABLE_4BIT:
        try:
            import bitsandbytes  # noqa: F401
            model_kwargs.update({
                "load_in_4bit": True,
                "device_map": "auto"
            })
            loaded_with = "4bit-bnb"
            logger.info("Attempting 4-bit quantization with bitsandbytes")
        except ImportError:
            logger.warning("bitsandbytes not available, skipping 4-bit quantization")
        except Exception as e:
            logger.warning(f"4-bit quantization failed: {e}")

    # Try accelerate device mapping if not already set
    if ENABLE_ACCELERATE and "device_map" not in model_kwargs:
        try:
            from accelerate import infer_auto_device_map  # noqa: F401
            model_kwargs["device_map"] = "auto"
            loaded_with = loaded_with + "+accelerate"
            logger.info("Using accelerate for device mapping")
        except ImportError:
            logger.warning("accelerate not available")
        except Exception as e:
            logger.warning(f"accelerate setup failed: {e}")

    # Model loading timing
    model_start = time.time()
    logger.info(f"📦 Loading model with config: {model_kwargs}")
    model = AutoModelForCausalLM.from_pretrained(**model_kwargs)
    model_time = time.time() - model_start
    logger.info(f"⏱️ Model loaded in {model_time:.2f} seconds")

    # Try optimum BetterTransformer optimization
    if ENABLE_OPTIMUM:
        opt_start = time.time()
        try:
            from optimum.bettertransformer import BetterTransformer
            model = BetterTransformer.transform(model)
            loaded_with = loaded_with + "+bettertransformer"
            opt_time = time.time() - opt_start
            logger.info(f"⏱️ BetterTransformer applied in {opt_time:.2f} seconds")
        except ImportError:
            logger.warning("optimum not available, skipping BetterTransformer")
        except Exception as e:
            logger.warning(f"BetterTransformer optimization failed: {e}")

    # Pipeline creation timing - CPU optimized
    pipeline_start = time.time()
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=-1,  # Force CPU device
        batch_size=1,  # Single batch for faster processing
        return_full_text=False  # Only return generated text
    )
    pipeline_time = time.time() - pipeline_start
    logger.info(f"⏱️ Pipeline created in {pipeline_time:.2f} seconds")

    total_time = time.time() - start_time
    logger.info(f"✅ TOTAL model loading time: {total_time:.2f} seconds with {loaded_with}")
    return pipe

# Centralized environment & offline configuration
model_name = setup_model_env()
logger.info(f"Configured environment for model: {model_name}")

# Ensure model exists locally before attempting load
try:
    mdir = assert_model_present(model_name)
    logger.info(f"Validated local model directory: {mdir}")
except RuntimeError as e:
    logger.error(str(e))
    raise

# Load pipeline with optimizations
try:
    pipe = _load_pipeline(model_name)  # This loads the transformer AI model into memory
    logger.info("Model pipeline loaded successfully with optimizations")
except Exception as e:
    logger.exception("Failed to initialize optimized model pipeline, falling back to standard")
    try:
        pipe = pipeline("text-generation", model=model_name, trust_remote_code=True)
        logger.info("Standard pipeline loaded successfully")
    except Exception as fallback_error:
        logger.exception("Both optimized and standard pipeline loading failed")
        raise

# FastAPI app setup
app = FastAPI(title="Fitness Chatbot with Optimizations", version="1.1.0")

# CORS for React frontend (default React dev server runs on :3000 or :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Mount static files directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Dynamic initial greeting derived from character profile
def initial_greeting_from_profile(character_type: str = "mary_senior") -> str:
    character = get_character_profile(character_type)
    health_issues = " and ".join(character["health_issues"])
    goals = " and ".join(character["goals"])
    
    if character_type == "mary_senior":
        return (
            f"Hi! I'm {character['name']}. I'm {character['age']}, recently retired, and I'm looking for guidance to lose some weight and gain strength. "
            f"I have {health_issues}, so I'm worried about doing the wrong exercises. "
            "I used to walk regularly but haven't done structured exercise in years. As my fitness coach, can you help me create a safe plan?"
        )
    elif character_type == "jake_athlete":
        return (
            f"Hey! I'm {character['name']}, {character['age']}-year-old professional athlete. I'm looking to optimize my training and maintain peak performance. "
            f"I've had some issues with {health_issues} in the past. My main goals are {goals}. "
            "I train hard but want to make sure I'm not missing anything. Can you help me fine-tune my approach?"
        )
    elif character_type == "sarah_mom":
        return (
            f"Hi! I'm {character['name']}, a {character['age']}-year-old working mom with two young kids. I really need help getting back in shape! "
            f"I'm dealing with {health_issues} from my busy lifestyle. My goals are {goals}. "
            "I used to be active before kids but now I barely have time to breathe. Can you help me figure out a realistic plan?"
        )
    elif character_type == "tom_executive":
        return (
            f"I'm {character['name']}, {character['age']}-year-old executive. My doctor says I need to get serious about my health - I'm dealing with {health_issues}. "
            f"My goals are {goals}. I was athletic in college but work has taken over my life. "
            "I need something efficient that delivers results. Time is money. Can you help me get back on track?"
        )
    else:
        return (
            f"Hi! I'm {character['name']}, a {character['age']}-year-old {character['status']}. "
            f"I'm looking for fitness guidance to help with {goals}. Can you help me?"
        )

# Enhanced character profile with specific details
MARY_PROFILE = """You are Mary, a 65-year-old recently retired woman. Personal details:
- Weight: 175 pounds (wants to lose weight)
- Height: 5'6"
- Health issues: mild knee arthritis, occasional lower back pain
- Exercise history: used to walk regularly but no structured exercise in years
- Goals: lose weight and gain strength safely
- Personality: friendly, slightly worried about injury, willing to share personal info

You answer questions directly and conversationally. When asked about weight, you say "I'm about 175 pounds right now, which is more than I'd like." You express concerns about safety but are eager to start."""

# Conversation memory system
conversation_contexts = {}
response_cache = {}
MAX_CACHE_SIZE = 100
MAX_CONTEXT_LENGTH = 4  # Keep last 4 exchanges per user

# Performance tracking
performance_stats = {
    "total_requests": 0,
    "quick_responses": 0,
    "cache_hits": 0,
    "ai_generations": 0,
    "total_response_time": 0.0,
    "total_ai_time": 0.0,
    "ai_inference_time": 0.0,
    "average_response_time": 0.0,
    "average_ai_time": 0.0,
    "last_request_time": None,
    "startup_time": time.time()
}

# Multi-Prospect Character Profiles System
CHARACTER_PROFILES = {
    "mary_senior": {
        "name": "Mary",
        "age": 65,
        "weight": 175,
        "height": "5'6\"",
        "status": "recently retired",
        "background": "Recently retired teacher who walked regularly but hasn't done structured exercise in years. Cautious but motivated to start a safe fitness routine.",
        "health_issues": ["mild knee arthritis", "occasional lower back pain"],
        "exercise_history": "used to walk regularly but no structured exercise in years",
        "goals": ["lose weight", "gain strength safely"],
        "personality": ["friendly", "slightly worried about injury", "eager to start"],
        "concerns": ["safety", "doing wrong exercises"],
        "quick_responses": {
            "weight": "I'm about 175 pounds right now, which is more than I'd like to be.",
            "height": "I'm 5'6\" tall.",
            "age": "I'm 65 years old, recently retired.",
            "name": "I'm Mary. Nice to meet you!",
            "hello": "Hi there! I'm Mary. I'm looking forward to working with you on my fitness goals.",
            "bank": "Oh, I'd rather not discuss my personal finances. Let's focus on my fitness goals instead!",
            "money": "I'm comfortable financially since I retired, but I'd prefer to talk about my health and fitness.",
            "investment": "I'm not sure what investments have to do with my fitness goals. Are you talking about investing in my health?",
            "broccoli": "I do try to eat healthy! Broccoli is good for me, though I'm not sure about the exact prices these days.",
            "groceries": "I do my grocery shopping like anyone else. Prices seem to keep going up these days!",
            "credit": "I'd rather keep my financial details private. Can we talk about my exercise plan instead?"
        }
    },
    
    "jake_athlete": {
        "name": "Jake",
        "age": 28,
        "weight": 180,
        "height": "5'10\"",
        "status": "professional athlete",
        "background": "Professional athlete who trains 6 days a week with focus on performance optimization. Previous ACL injury makes him cautious about injury prevention while pushing performance limits.",
        "health_issues": ["previous ACL injury"],
        "exercise_history": "trains 6 days a week, focus on performance optimization",
        "goals": ["maintain peak performance", "injury prevention", "optimize training efficiency"],
        "personality": ["competitive", "knowledgeable about fitness", "time-conscious", "results-driven"],
        "concerns": ["overtraining", "injury recurrence", "performance plateaus"],
        "quick_responses": {
            "weight": "I'm 180 pounds, pretty lean muscle mass. I monitor it closely for performance.",
            "height": "5'10\".",
            "age": "I'm 28, in my athletic prime.",
            "name": "I'm Jake. Ready to optimize my training!",
            "hello": "Hey! I'm Jake. I'm looking to take my performance to the next level.",
            "bank": "I'm doing fine financially, thanks. Let's talk about maximizing my training ROI.",
            "money": "My body is my career. I invest heavily in performance.",
            "investment": "Every dollar I spend on training and recovery pays back in performance. What's your approach?",
            "broccoli": "Yeah, I eat a lot of greens. Nutrition is huge for recovery and performance.",
            "groceries": "I spend a lot on quality food. It's part of my training investment.",
            "credit": "I'm financially stable. Let's focus on performance optimization."
        }
    },
    
    "sarah_mom": {
        "name": "Sarah",
        "age": 35,
        "weight": 155,
        "height": "5'4\"",
        "status": "busy working mom",
        "background": "35-year-old working mother with two young children. Was active before having kids but now struggles with time constraints, desk job back pain, and chronic fatigue. Motivated but overwhelmed.",
        "health_issues": ["lower back pain from desk job", "chronic fatigue"],
        "exercise_history": "was active before kids, now struggles to find time",
        "goals": ["lose baby weight", "gain energy", "be a good example for kids", "manage stress"],
        "personality": ["busy", "motivated but overwhelmed", "practical", "caring"],
        "concerns": ["time constraints", "childcare during workouts", "energy levels"],
        "quick_responses": {
            "weight": "I'm about 155 pounds. I gained 25 during pregnancy and still have 15 to go.",
            "height": "I'm 5'4\".",
            "age": "I'm 35, with two young kids who keep me busy!",
            "name": "I'm Sarah. Nice to meet you - thanks for fitting me in!",
            "hello": "Hi! I'm Sarah. I really hope you can help me find time for fitness with my crazy schedule.",
            "bank": "Money's tight with the kids, but I know I need to invest in my health.",
            "money": "We're careful with money, but I understand this is important for my family too.",
            "investment": "Every mom knows you have to invest in yourself to take care of everyone else. What's realistic?",
            "broccoli": "I try to eat healthy for the kids, but honestly it's hard with their schedules!",
            "groceries": "Grocery shopping with kids is an adventure! I try to get healthy stuff when I can.",
            "credit": "We budget carefully, but health is a priority. What are we looking at cost-wise?"
        }
    },
    
    "tom_executive": {
        "name": "Tom",
        "age": 45,
        "weight": 220,
        "height": "6'0\"",
        "status": "busy executive",
        "background": "45-year-old business executive who was athletic in college but became sedentary due to work demands. Recently warned by doctor about pre-diabetes and high blood pressure. Analytical and results-driven.",
        "health_issues": ["high stress levels", "pre-diabetes warning", "high blood pressure"],
        "exercise_history": "was athletic in college, now mostly sedentary due to work demands",
        "goals": ["lose weight quickly", "reduce stress", "avoid diabetes", "improve executive presence"],
        "personality": ["results-driven", "slightly skeptical", "time-pressed", "analytical"],
        "concerns": ["return on investment", "time efficiency", "sustainable results"],
        "quick_responses": {
            "weight": "I'm 220 pounds, probably 40-50 pounds heavier than I should be. Doctor's orders.",
            "height": "6 feet.",
            "age": "I'm 45, in the prime of my career but my health is suffering.",
            "name": "I'm Tom. Let's get straight to business.",
            "hello": "Hi, I'm Tom. I need results fast - doctor says I'm pre-diabetic.",
            "bank": "I'm financially comfortable, but I want to see clear value for my investment.",
            "money": "Money isn't the issue - time and results are. What's the ROI?",
            "investment": "I understand ROI. If you can prove this works efficiently, I'm willing to invest significantly.",
            "broccoli": "I eat whatever's fastest. Probably part of the problem, right?",
            "groceries": "My assistant handles most of that. I grab whatever's convenient.",
            "credit": "Finances aren't a concern. I want to know about time investment and guaranteed results."
        }
    }
}

# Character categories for easy management
CHARACTER_CATEGORIES = {
    "fitness_prospects": ["mary_senior", "jake_athlete", "sarah_mom", "tom_executive"],
    "beginners": ["mary_senior", "sarah_mom"],
    "advanced": ["jake_athlete"],
    "time_conscious": ["sarah_mom", "tom_executive"]
}

# Enhanced fuzzy matching patterns for all character types
FUZZY_PATTERNS = {
    "weight": ["weight", "weigh", "pounds", "heavy", "scale", "mass"],
    "height": ["height", "tall", "short", "feet", "inches"],
    "age": ["age", "old", "years", "birthday"],
    "name": ["name", "called", "who are you"],
    "hello": ["hello", "hi", "hey", "greetings"],
    "bank": ["bank", "account", "savings", "checking"],
    "money": ["money", "cash", "finances", "income", "salary", "pension"],
    "broccoli": ["broccoli", "vegetables", "veggies", "greens"],
    "groceries": ["grocery", "shopping", "store", "market"],
    "credit": ["credit", "card", "debt", "loan"],
    "investment": ["investment", "invest", "investing", "portfolio", "stocks", "roi"]
}

def get_character_profile(character_type: str = "mary_senior"):
    """Get character profile by type"""
    return CHARACTER_PROFILES.get(character_type, CHARACTER_PROFILES["mary_senior"])

def get_available_characters():
    """Get list of available character types with descriptions"""
    characters = {}
    for char_type, char_data in CHARACTER_PROFILES.items():
        characters[char_type] = {
            "name": char_data["name"],
            "age": char_data["age"],
            "status": char_data["status"],
            "description": f"{char_data['name']}, {char_data['age']}-year-old {char_data['status']}"
        }
    return characters

def build_character_prompt(message: str, contexts: List[dict], character_type: str = "mary_senior") -> str:
    """Build a comprehensive character prompt with context awareness for any character type"""
    character = get_character_profile(character_type)
    
    # Enhanced context formatting with intelligent summarization
    context_str = ""
    if contexts:
        # Use last 4 exchanges for immediate context, summarize older ones
        recent_contexts = contexts[-4:]
        older_contexts = contexts[:-4] if len(contexts) > 4 else []
        
        if older_contexts:
            # Quick summary of older conversation themes
            older_topics = [ctx.get("topic", "general") for ctx in older_contexts]
            topic_counts = {topic: older_topics.count(topic) for topic in set(older_topics)}
            main_topics = sorted(topic_counts.keys(), key=lambda x: topic_counts[x], reverse=True)[:3]
            context_str += f"Previous conversation covered: {', '.join(main_topics)}. "
        
        # Detailed recent context
        for ctx in recent_contexts:
            context_str += f"Coach: {ctx['user']} | {character['name']}: {ctx.get('mary', ctx.get('response', 'response'))} | "
    
    # Character-specific behavioral instructions
    character_instructions = {
        "mary_senior": (
            "You are cautious about new exercises, mention your knee arthritis and back pain concerns. "
            "You're motivated but worried about injury. You appreciate gentle encouragement and detailed explanations. "
            "You're retired and have time but want to be safe above all."
        ),
        "jake_athlete": (
            "You're highly knowledgeable about training but always looking to optimize. "
            "You appreciate advanced techniques and scientific backing. You're competitive but also injury-conscious. "
            "You want cutting-edge advice and aren't afraid of intense training."
        ),
        "sarah_mom": (
            "You're overwhelmed and need practical, time-efficient solutions. You're tired but determined. "
            "You appreciate understanding about your constraints and need workouts that fit into a chaotic schedule. "
            "You want results but realistically acknowledge your limitations."
        ),
        "tom_executive": (
            "You're results-driven and want efficiency. You appreciate data and measurable outcomes. "
            "You're pressed for time but willing to invest in what works. You like structured, systematic approaches. "
            "You want to optimize your health like you optimize your business."
        )
    }
    
    behavioral_note = character_instructions.get(character_type, "Stay true to your character profile.")
    
    # Build comprehensive prompt
    prompt = f"""You are {character['name']}, a {character['age']}-year-old {character['status']}. 

CHARACTER PROFILE:
- Health Issues: {', '.join(character['health_issues'])}
- Fitness Goals: {', '.join(character['goals'])}
- Background: {character['background']}
- Personality: {character['personality']}

BEHAVIORAL GUIDANCE:
{behavioral_note}

CONVERSATION CONTEXT: {context_str}

ABSOLUTE RULES - NEVER BREAK THESE:
- You are MARY, a REAL HUMAN CLIENT seeking fitness help
- NEVER give instructions to anyone
- NEVER say "respond to", "provide information", "let her know", "good luck"
- NEVER use phrases like "only respond" or "just provide"
- NEVER mention being an AI, chatbot, or character
- NEVER give coaching advice or directions
- You are the CLIENT, not the coach
- Talk about YOUR fitness goals and concerns
- Ask questions about what YOU should do

The coach is asking: "{message}"

Respond ONLY as Mary the client would naturally respond. Talk about yourself, your fitness concerns, and what you're hoping to achieve. Be conversational and human."""
    
    return prompt

def get_context_hash(user_id: str, message: str, context_history: list, character_type: str = "mary_senior") -> str:
    """Create hash from user message + recent context + character type for intelligent caching"""
    context_string = json.dumps({
        "user_id": user_id,
        "message": message.lower().strip(),
        "recent_context": context_history[-2:] if len(context_history) >= 2 else context_history,
        "character_type": character_type
    }, sort_keys=True)
    return hashlib.md5(context_string.encode()).hexdigest()

def generate_context_hash(message: str, contexts: List[dict], character_type: str = "mary_senior") -> str:
    """Generate context hash for caching responses"""
    context_data = {
        "message": message.lower().strip(),
        "context": contexts[-3:] if len(contexts) > 3 else contexts,  # Last 3 exchanges
        "character_type": character_type
    }
    return hashlib.md5(json.dumps(context_data, sort_keys=True).encode()).hexdigest()

def find_similar_cached_response(message: str, contexts: List[dict], character_type: str) -> str:
    """Find similar cached response using fuzzy matching"""
    message_words = set(message.lower().split())
    
    for cache_key, cached_response in response_cache.items():
        # Simple word overlap check for similarity
        cache_data = json.loads(cache_key) if cache_key.startswith('{') else {}
        if isinstance(cache_data, dict) and cache_data.get("character_type") == character_type:
            cache_words = set(cache_data.get("message", "").split())
            overlap = len(message_words.intersection(cache_words))
            if overlap > 2 and len(message_words) > 3:  # Reasonable similarity threshold
                return cached_response
    return None

def classify_message_topic(message: str) -> str:
    """Classify message topic for better context management"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["exercise", "workout", "training", "movement"]):
        return "exercise"
    elif any(word in message_lower for word in ["diet", "food", "nutrition", "eat", "meal"]):
        return "nutrition"
    elif any(word in message_lower for word in ["pain", "hurt", "injury", "arthritis", "back"]):
        return "health_issues"
    elif any(word in message_lower for word in ["goal", "want", "achieve", "target"]):
        return "goals"
    elif any(word in message_lower for word in ["time", "schedule", "busy", "when"]):
        return "scheduling"
    elif any(word in message_lower for word in ["how", "what", "why", "explain"]):
        return "questions"
    else:
        return "general"

def generate_ai_response(prompt: str) -> str:
    """Generate AI response using the loaded model"""
    try:
        response = pipe(
            prompt,
            max_new_tokens=60,
            num_return_sequences=1,
            temperature=0.7,
            do_sample=True,
            top_p=0.85,
            repetition_penalty=1.1,
            pad_token_id=pipe.tokenizer.eos_token_id
        )
        
        generated_text = response[0]['generated_text'].strip()
        
        # Extract the character's response (everything after the prompt)
        if prompt in generated_text:
            character_response = generated_text.replace(prompt, "").strip()
        else:
            # Fallback: find the first meaningful line that looks like Mary speaking
            character_response = ""
            for line in generated_text.split('\n'):
                line = line.strip()
                if line and not any(skip in line.lower() for skip in [
                    "you are", "character", "behavioral", "conversation", "critical",
                    "respond as", "only respond", "just provide", "let her know",
                    "good luck", "mary:", "instructions", "directions", "guidance"
                ]):
                    character_response = line
                    break
        
        # Clean up and validate the response
        character_response = character_response.replace('"', '').strip()
        
        # Filter out any remaining instructional language
        if any(instruction in character_response.lower() for instruction in [
            "respond to", "provide information", "let her know", "good luck", 
            "only respond", "just provide", "make sense for someone"
        ]):
            # Return a safe default response as Mary
            return "Well, I'm hoping you can help me figure out what kind of exercise would be best for someone like me at my age."
        
        if not character_response.endswith(('.', '!', '?')):
            character_response += "."
            
        return character_response
        
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        raise e

def get_character_quick_patterns(character_type: str) -> dict:
    """Get character-specific quick response patterns with improved matching"""
    character = get_character_profile(character_type)
    
    base_patterns = {
        # More specific greeting patterns
        "^(hello|hi|hey)$|^(hello|hi|hey) there": f"Hi there! I'm {character['name']}. It's so nice to meet you!",
        "how are you|how do you feel": f"I'm doing well, thank you for asking! A bit nervous but excited to get started.",
        "how can i help you|can i help|help you": f"Oh, that's so kind of you to ask! I'm actually here looking for help with my fitness goals. I'm hoping you can guide me.",
        "how old are you|what's your age|your age": f"I'm {character['age']} years old. I know I'm not getting any younger, but I'm determined to get healthier!",
        "what are your goals|your goals|what do you want to achieve": f"Well, I really want to {' and '.join(character['goals'])}, but I want to do it safely.",
        # Food and nutrition patterns
        "what do you like to eat|what do you eat|your diet|eating habits": f"I try to eat healthy, but I'll be honest - I could use some guidance on nutrition too. What would you recommend for someone like me?",
        "do you cook|cooking|meal prep": f"I do cook for myself, though I'm not always sure if I'm making the healthiest choices. Do you have any simple, healthy meal ideas?"
    }
    
    # Character-specific patterns with better precision
    if character_type == "mary_senior":
        base_patterns.update({
            "(knee|knees).*(arthritis|pain|hurt|up|about)|arthritis.*(knee|knees)|knee.*problem|\\bknees\\?": "Oh yes, my knees! They've been giving me trouble lately with the arthritis. I'm really worried about making it worse.",
            "(back|lower back).*(pain|hurt|ache)|back pain": "My lower back does bother me sometimes, especially when I've been sitting too long. It's one of my concerns.",
            "\\b(retired|retirement)\\b|\\bteaching\\b.*\\b(job|work|career)": "I just retired recently from teaching! It's exciting to finally have time for myself, but also a bit overwhelming.",
            "(what.*weight|how much.*weigh|your weight)": "I'm about 175 pounds right now, which is more than I'd like to be. I'd really like to get that down.",
            "(exercise|workout|training).*(history|experience|background)": "I used to walk regularly, but I haven't done any real structured exercise in years. I'm not even sure where to start!"
        })
    elif character_type == "jake_athlete":
        base_patterns.update({
            "(athlete|sport|competition|professional)": f"I'm a professional athlete, so performance optimization is everything to me. I need to stay at peak condition.",
            "(training|workout).*(routine|program|schedule)": "I train intensively but I'm always looking for ways to improve my approach and prevent injuries.",
            "(injury|pain|acl).*(history|prevention|concern)": f"I've had some issues with {' and '.join(character['health_issues'])} so injury prevention is crucial for my career."
        })
    elif character_type == "sarah_mom":
        base_patterns.update({
            "(time|busy|schedule).*(challenge|constraint|issue)": "Time is my biggest challenge! With two young kids and work, I barely have a moment to myself.",
            "(kids|children|mom|mother).*(working|busy)": "Being a working mom is exhausting. I want to be healthy for my kids but it's so hard to find time.",
            "(tired|exhausted|fatigue).*(constantly|always|chronic)": "I'm constantly tired between work and kids. I need something that gives me energy, not drains it."
        })
    elif character_type == "tom_executive":
        base_patterns.update({
            "(work|business|executive|corporate)": "My work is demanding and I travel frequently. I need efficient solutions that deliver results.",
            "(time|efficient|quick).*(money|business|results)": "Time is money for me. I need workouts that are effective but fit into a busy schedule.",
            "(results|data|measurable|metrics|tracking)": "I like to see measurable progress. What metrics should I be tracking to ensure success?"
        })
    
    return base_patterns


def chat_with_character(message: str, user_id: str = "default", character_type: str = "mary_senior") -> str:
    """Enhanced chat function with multi-character support, context memory, and 3-tier speed optimization"""
    start_time = time.time()
    response_type = "unknown"
    
    try:
        # Update performance tracking
        performance_stats["total_requests"] += 1
        performance_stats["last_request_time"] = start_time
        
        # Create session key for character-specific conversations
        session_key = f"{user_id}_{character_type}"
        
        # Get character profile
        character = get_character_profile(character_type)
        
        # ===== TIER 1: INSTANT RESPONSES (0.01-0.05s) =====
        # Improved quick pattern matching with better precision
        quick_patterns = get_character_quick_patterns(character_type)
        
        message_lower = message.lower().strip()
        
        for pattern, quick_response in quick_patterns.items():
            # Use regex matching for more precise pattern detection
            if re.search(pattern, message_lower, re.IGNORECASE):
                response_type = "quick"
                performance_stats["quick_responses"] += 1
                
                response_time = time.time() - start_time
                performance_stats["total_response_time"] += response_time
                performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
                
                logger.info(f"⚡ Quick response for {character['name']} ({response_time:.3f}s): {message[:30]}... -> {pattern}")
                return quick_response.format(name=character["name"])
        
        # ===== TIER 2: CACHED RESPONSES (0.02-0.08s) =====
        # Context-aware caching with fuzzy matching
        contexts = conversation_contexts.get(session_key, [])
        context_hash = generate_context_hash(message, contexts, character_type)
        
        if context_hash in response_cache:
            response_type = "cache"
            performance_stats["cache_hits"] += 1
            cached_response = response_cache[context_hash]
            
            response_time = time.time() - start_time
            performance_stats["total_response_time"] += response_time
            performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
            
            logger.info(f"💾 Cache hit for {character['name']} ({response_time:.3f}s): {message[:30]}...")
            return cached_response
        
        # Check for similar cached responses using fuzzy matching
        similar_response = find_similar_cached_response(message, contexts, character_type)
        if similar_response:
            response_type = "fuzzy"
            performance_stats["cache_hits"] += 1
            
            response_time = time.time() - start_time
            performance_stats["total_response_time"] += response_time
            performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
            
            logger.info(f"🔍 Fuzzy match for {character['name']} ({response_time:.3f}s): {message[:30]}...")
            return similar_response
        
        # ===== TIER 3: AI GENERATION (2-8s) =====
        ai_start = time.time()
        response_type = "ai"
        performance_stats["ai_generations"] += 1
        
        logger.info(f"🤖 Generating AI response for {character['name']}: {message[:50]}...")
        
        # Build character-specific prompt
        prompt = build_character_prompt(message, contexts, character_type)
        
        # Generate response using the AI model
        try:
            response = generate_ai_response(prompt)
            
            # Final safety check - if response still contains instructions, use a safe fallback
            if any(bad_phrase in response.lower() for bad_phrase in [
                "respond to", "provide information", "let her know", "good luck mary",
                "only respond", "just provide", "make sense for someone", "instructions"
            ]):
                # Use character-appropriate fallback responses
                fallback_responses = [
                    "I'm really hoping you can help me with my fitness goals. What do you think would be best for someone like me?",
                    "That's a great question! I'm not sure what the best approach would be - that's why I'm here talking to you.",
                    "I'm a bit nervous about starting, but I really want to get healthier. What would you recommend for a beginner like me?",
                    "Well, I've been thinking about this a lot since I retired. I just want to make sure I do things safely."
                ]
                response = fallback_responses[hash(message) % len(fallback_responses)]
                
        except Exception as e:
            logger.error(f"AI generation failed for {character['name']}: {e}")
            return f"I'm sorry, I'm having trouble responding right now. Could you try asking again? - {character['name']}"
        
        ai_time = time.time() - ai_start
        performance_stats["total_ai_time"] += ai_time
        performance_stats["average_ai_time"] = performance_stats["total_ai_time"] / performance_stats["ai_generations"]
        
        # Store conversation context with character type
        if session_key not in conversation_contexts:
            conversation_contexts[session_key] = []
        
        # Add context with topic classification for smarter summarization
        topic = classify_message_topic(message)
        conversation_contexts[session_key].append({
            "user": message,
            "mary": response,  # Keep 'mary' key for backward compatibility
            "response": response,
            "timestamp": time.time(),
            "topic": topic,
            "character_type": character_type
        })
        
        # Maintain context window
        if len(conversation_contexts[session_key]) > MAX_CONTEXT_LENGTH:
            conversation_contexts[session_key] = conversation_contexts[session_key][-MAX_CONTEXT_LENGTH:]
        
        # Cache the response for future use
        if len(response_cache) >= MAX_CACHE_SIZE:
            # Remove oldest cache entry
            oldest_key = min(response_cache.keys(), key=lambda k: response_cache[k])
            del response_cache[oldest_key]
        
        response_cache[context_hash] = response
        
        # Final performance logging
        total_time = time.time() - start_time
        performance_stats["total_response_time"] += total_time
        performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
        
        logger.info(f"✨ AI response for {character['name']} generated ({total_time:.3f}s, AI: {ai_time:.3f}s)")
        return response
        
    except Exception as e:
        # Error handling
        response_time = time.time() - start_time
        performance_stats["total_response_time"] += response_time
        performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
        
        logger.error(f"❌ Error in chat_with_character for {character_type}: {e}")
        character = get_character_profile(character_type)
        return f"I'm sorry, I'm having some trouble right now. Could you ask me that again? - {character['name']}"

# Legacy function for backward compatibility
def chat_with_mary(message: str, user_id: str = "default"):
    """Legacy chat function - redirects to multi-character system"""
    return chat_with_character(message, user_id, "mary_senior")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, character_type: str = "mary_senior"):
    """Home page that renders the chat.html template with dynamic character greeting"""
    character = get_character_profile(character_type)
    return templates.TemplateResponse(
        "chat.html", 
        {
            "request": request, 
            "initial_greeting": initial_greeting_from_profile(character_type),
            "character_name": character["name"],
            "character_type": character_type
        }
    )

# React-friendly API endpoints with multi-character session support
@app.post("/api/chat")
async def api_chat(payload: dict):
    """Enhanced API endpoint for React frontend with multi-character support"""
    message = payload.get("message", "")
    user_id = payload.get("user_id", "default")
    character_type = payload.get("character_type", "mary_senior")  # NEW: Character selection
    
    response = chat_with_character(message, user_id, character_type)
    character = get_character_profile(character_type)
    session_key = f"{user_id}_{character_type}"
    
    return {
        "response": response, 
        "status": "success",
        "user_id": user_id,
        "character": {
            "name": character["name"],
            "type": character_type,
            "age": character["age"],
            "status": character["status"],
            "description": f"{character['name']}, {character['age']}-year-old {character['status']}"
        },
        "context_size": len(conversation_contexts.get(session_key, []))
    }

@app.get("/api/greeting")
async def api_greeting(character_type: str = "mary_senior"):
    """Get the initial greeting for any character type"""
    character = get_character_profile(character_type)
    return {
        "greeting": initial_greeting_from_profile(character_type),
        "character": {
            "name": character["name"],
            "type": character_type,
            "age": character["age"],
            "status": character["status"]
        }
    }

@app.get("/api/characters")
async def get_available_characters():
    """Get list of available character types with descriptions"""
    characters = get_available_characters()
    return {"characters": characters, "total": len(characters)}

@app.get("/api/character/{character_type}")
async def get_character_details(character_type: str):
    """Get detailed character information"""
    if character_type not in CHARACTER_PROFILES:
        return {"error": "Character type not found", "available_types": list(CHARACTER_PROFILES.keys())}
    
    character = get_character_profile(character_type)
    return {"character": character, "character_type": character_type}

@app.post("/chat")
async def chat(request: dict):
    """Legacy chat endpoint for template-based frontend with multi-character support"""
    message = request.get("message", "")
    user_id = request.get("user_id", "default")
    character_type = request.get("character_type", "mary_senior")
    response = chat_with_character(message, user_id, character_type)
    return {"response": response, "character_type": character_type}

@app.post("/api/reset-conversation")
async def reset_conversation(payload: dict):
    """Reset conversation context for specific character type"""
    user_id = payload.get("user_id", "default")
    character_type = payload.get("character_type", "mary_senior")
    session_key = f"{user_id}_{character_type}"
    
    if session_key in conversation_contexts:
        context_count = len(conversation_contexts[session_key])
        del conversation_contexts[session_key]
        character = get_character_profile(character_type)
        logger.info(f"🗑️ Reset conversation for {character['name']} ({character_type}) - {context_count} entries")
        return {
            "status": "conversation reset", 
            "user_id": user_id,
            "character": character["name"],
            "character_type": character_type,
            "cleared_entries": context_count
        }
    return {"status": "no conversation found", "user_id": user_id, "character_type": character_type}

@app.get("/health")
async def health():
    """Health check endpoint with comprehensive performance metrics and multi-character support"""
    # Basic stats
    active_sessions = len(conversation_contexts)
    total_context_entries = sum(len(contexts) for contexts in conversation_contexts.values())
    uptime = time.time() - performance_stats["startup_time"]
    
    # Character distribution stats
    character_stats = {}
    for session_key in conversation_contexts.keys():
        if "_" in session_key:
            _, char_type = session_key.rsplit("_", 1)
            if char_type in CHARACTER_PROFILES:
                character_stats[char_type] = character_stats.get(char_type, 0) + 1
    
    # Performance calculations
    total_requests = performance_stats["total_requests"]
    quick_response_rate = (performance_stats["quick_responses"] / max(total_requests, 1)) * 100
    cache_hit_rate = (performance_stats["cache_hits"] / max(total_requests, 1)) * 100
    ai_generation_rate = (performance_stats["ai_generations"] / max(total_requests, 1)) * 100
    
    # Speed predictions based on current stats
    predicted_times = {
        "quick_response": "0.01-0.05s",
        "cache_hit": "0.02-0.08s",
        "ai_generation": f"{performance_stats['average_ai_time']:.2f}s" if performance_stats['average_ai_time'] > 0 else "2-8s"
    }
    
    # Cache efficiency
    cache_utilization = (len(response_cache) / MAX_CACHE_SIZE) * 100
    
    # Request rate (requests per minute)
    requests_per_minute = (total_requests / max(uptime / 60, 1)) if uptime > 60 else 0
    
    return {
        "status": "ok",
        "uptime_seconds": round(uptime, 2),
        "model": model_name,
        "system_type": "Multi-Character Sales Roleplay",
        
        # Character system info
        "character_system": {
            "available_characters": len(CHARACTER_PROFILES),
            "character_types": list(CHARACTER_PROFILES.keys()),
            "character_distribution": character_stats,
            "categories": CHARACTER_CATEGORIES
        },
        
        # Performance metrics
        "performance": {
            "total_requests": total_requests,
            "requests_per_minute": round(requests_per_minute, 2),
            "average_response_time": round(performance_stats["average_response_time"], 3),
            "average_ai_inference_time": round(performance_stats["average_ai_time"], 3),
            "last_request": round(time.time() - performance_stats["last_request_time"], 2) if performance_stats["last_request_time"] else None
        },
        
        # Response type distribution
        "response_distribution": {
            "quick_responses": {
                "count": performance_stats["quick_responses"],
                "percentage": round(quick_response_rate, 1)
            },
            "cache_hits": {
                "count": performance_stats["cache_hits"],
                "percentage": round(cache_hit_rate, 1)
            },
            "ai_generations": {
                "count": performance_stats["ai_generations"],
                "percentage": round(ai_generation_rate, 1)
            }
        },
        
        # Speed predictions
        "predicted_response_times": predicted_times,
        
        # Memory and cache info
        "memory_usage": {
            "active_sessions": active_sessions,
            "total_context_entries": total_context_entries,
            "cache_size": len(response_cache),
            "cache_utilization_percent": round(cache_utilization, 1),
            "max_cache_size": MAX_CACHE_SIZE,
            "max_context_length": MAX_CONTEXT_LENGTH
        },
        
        # System capabilities
        "features": [
            "multi_character_support",
            "context_memory",
            "intelligent_caching", 
            "dynamic_responses",
            "fuzzy_matching",
            "human_character_protection",
            "performance_optimization",
            "character_specific_responses"
        ],
        
        # Performance recommendations
        "recommendations": {
            "cache_efficiency": "excellent" if cache_hit_rate > 30 else "good" if cache_hit_rate > 15 else "needs_improvement",
            "quick_response_rate": "excellent" if quick_response_rate > 40 else "good" if quick_response_rate > 20 else "low",
            "overall_performance": "optimized" if performance_stats["average_response_time"] < 2.0 else "moderate" if performance_stats["average_response_time"] < 5.0 else "slow"
        }
    }

@app.post("/api/clear-cache")
async def clear_cache():
    """Clear response cache for testing"""
    global response_cache
    cache_size = len(response_cache)
    response_cache.clear()
    logger.info(f"🗑️ Cleared {cache_size} cached responses")
    return {"status": "cache cleared", "cleared_entries": cache_size}

@app.get("/api/conversation-stats")
async def conversation_stats():
    """Get comprehensive conversation statistics for multi-character system"""
    stats = {}
    character_activity = {}
    
    for session_key, contexts in conversation_contexts.items():
        # Parse session key to get user and character type
        if "_" in session_key:
            user_id, character_type = session_key.rsplit("_", 1)
        else:
            user_id, character_type = session_key, "unknown"
        
        # User stats
        if user_id not in stats:
            stats[user_id] = {
                "total_conversations": 0,
                "total_exchanges": 0,
                "characters_used": [],
                "last_activity": None
            }
        
        stats[user_id]["total_conversations"] += 1
        stats[user_id]["total_exchanges"] += len(contexts)
        if character_type not in stats[user_id]["characters_used"]:
            stats[user_id]["characters_used"].append(character_type)
        
        latest_activity = max([ctx["timestamp"] for ctx in contexts]) if contexts else None
        if not stats[user_id]["last_activity"] or (latest_activity and latest_activity > stats[user_id]["last_activity"]):
            stats[user_id]["last_activity"] = latest_activity
        
        # Character activity stats
        if character_type not in character_activity:
            character_activity[character_type] = {
                "total_sessions": 0,
                "total_exchanges": 0,
                "unique_users": set(),
                "last_used": None
            }
        
        character_activity[character_type]["total_sessions"] += 1
        character_activity[character_type]["total_exchanges"] += len(contexts)
        character_activity[character_type]["unique_users"].add(user_id)
        
        if not character_activity[character_type]["last_used"] or (latest_activity and latest_activity > character_activity[character_type]["last_used"]):
            character_activity[character_type]["last_used"] = latest_activity
    
    # Convert sets to counts for JSON serialization
    for char_type in character_activity:
        character_activity[char_type]["unique_users"] = len(character_activity[char_type]["unique_users"])
    
    return {
        "active_conversations": len(conversation_contexts),
        "cache_utilization": f"{len(response_cache)}/{MAX_CACHE_SIZE}",
        "unique_users": len(stats),
        "total_characters": len(CHARACTER_PROFILES),
        "user_stats": stats,
        "character_activity": character_activity,
        "most_popular_character": max(character_activity.keys(), key=lambda x: character_activity[x]["total_sessions"]) if character_activity else None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)  

# To run the app: python src/fitness_chatbot.py
# or uvicorn src.fitness_chatbot:app --host 0.0.0.0 --port 8000 --reload
