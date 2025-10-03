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
from pathlib import Path
from typing import List, Dict

# Add utils to path
utils_path = str(Path(__file__).resolve().parent.parent / "utils")
if utils_path not in sys.path:
  sys.path.insert(0, utils_path)

# Project imports
from utils.env import setup_model_env, assert_model_present
from utils.paths import LOGS_DIR, MODEL_CACHE_DIR, TEMPLATES_DIR, STATIC_DIR
from utils.logger_config import setup_logging
from fallback_responses import generate_ai_response, toggle_fallback_responses

# System Configuration
logger = setup_logging(LOGS_DIR)

# Optimization flags - optimized for CPU performance
ENABLE_4BIT = os.environ.get("ENABLE_4BIT", "0") == "1"  # Disabled by default for CPU
ENABLE_ACCELERATE = os.environ.get("ENABLE_ACCELERATE", "0") == "1"  # Disabled by default
ENABLE_OPTIMUM = os.environ.get("ENABLE_OPTIMUM", "1") == "1"  # Keep this enabled

# AI Model Loading

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

# Model Initialization

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

# FastAPI Setup

# FastAPI app setup
app = FastAPI(title="AI Sales Training Chatbot", version="2.0.0")

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

# Character Profile & Data

def get_mary_greeting() -> str:
    mary = get_mary_profile()
    health_issues = " and ".join(mary["health_issues"])
    return (f"Hi! I'm {mary['name']}. I'm {mary['age']}, recently retired, and looking for fitness guidance. "
            f"I have {health_issues}, so I'm worried about safety. Can you help me create a safe plan?")

# Conversation memory system - pure AI driven with persistence
conversation_contexts = {}
MAX_CONTEXT_LENGTH = 4  # Keep last 4 exchanges per user

# Add conversation backup to prevent message loss
import json
from datetime import datetime

def save_conversation_backup():
    """Save conversations to backup file"""
    try:
        backup_data = {
            "timestamp": datetime.now().isoformat(),
            "conversations": {}
        }
        for key, contexts in conversation_contexts.items():
            # Convert to JSON-serializable format
            backup_data["conversations"][key] = [
                {
                    "user": ctx["user"],
                    "response": ctx["response"], 
                    "timestamp": ctx["timestamp"]
                }
                for ctx in contexts
            ]
        
        backup_file = LOGS_DIR / "conversation_backup.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)
        logger.debug(f"💾 Conversation backup saved with {len(conversation_contexts)} sessions")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save conversation backup: {e}")

def load_conversation_backup():
    """Load conversations from backup file"""
    try:
        backup_file = LOGS_DIR / "conversation_backup.json"
        if backup_file.exists():
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            global conversation_contexts
            conversation_contexts = backup_data.get("conversations", {})
            logger.info(f"📂 Loaded {len(conversation_contexts)} conversation sessions from backup")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load conversation backup: {e}")

# Load existing conversations on startup
load_conversation_backup()

# Performance tracking - simplified for AI-only system
performance_stats = {
    "total_requests": 0,
    "ai_generations": 0,
    "total_response_time": 0.0,
    "total_ai_time": 0.0,
    "average_response_time": 0.0,
    "average_ai_time": 0.0,
    "last_request_time": None,
    "startup_time": time.time(),
    "ai_failures": 0
}

# Mary's Character Profile
MARY_PROFILE = {
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
    "concerns": ["safety", "doing wrong exercises"]
}


# AI Prompt Generation

def get_mary_profile():
    """Get Mary's character profile"""
    return MARY_PROFILE

def build_mary_prompt(message: str, contexts: List[dict]) -> str:
    """Build AI prompt for Mary's character in sales training context."""
    mary = get_mary_profile()
    
    # Build conversation history for context
    conversation_history = ""
    if contexts:
        # Include last 3 exchanges for better context
        recent_contexts = contexts[-3:] if len(contexts) > 3 else contexts
        for ctx in recent_contexts:
            conversation_history += f"Salesperson: {ctx['user']}\nMary: {ctx.get('response', '')}\n\n"
    
    # Create comprehensive prompt for AI training with clear boundaries
    prompt = f"""You are Mary, a {mary['age']}-year-old {mary['status']} responding to a fitness salesperson. Answer ONLY as Mary would, staying in character.

MARY'S CURRENT SITUATION:
- Age: {mary['age']} years old (recently retired teacher)
- Health Issues: {', '.join(mary['health_issues'])} 
- Exercise History: {mary['exercise_history']}
- Main Concerns: {', '.join(mary['concerns'])}
- Goals: {', '.join(mary['goals'])}
- Personality: {', '.join(mary['personality'])}

CRITICAL INSTRUCTIONS:
- Answer the salesperson's question directly
- Mention your age-related limitations and health concerns when relevant
- Reference your {', '.join(mary['health_issues'])} if asked about restrictions
- Stay consistent with being a {mary['age']}-year-old retiree
- Express both interest AND safety concerns
- Keep response 1-2 sentences maximum
- Never ignore the question asked

{conversation_history}Salesperson: {message}

Mary (staying in character as a {mary['age']}-year-old with {', '.join(mary['health_issues'])}):"""
    
    return prompt

# The generate_ai_response function is imported from enhanced_responses.py


# Core Chat Functions

# Use MARY_PROFILE as the main character profile (defined above)
CHARACTER_PROFILE = MARY_PROFILE

def get_initial_greeting() -> str:
    """Generate Mary's initial AI greeting with caching."""
    global cached_greeting
    if cached_greeting:
        logger.info("📝 Using cached initial greeting")
        return cached_greeting

    mary = get_mary_profile()
    greeting_prompt = f"""You are Mary, a {mary['age']}-year-old retiree meeting a fitness salesperson for the first time.
Generate Mary's introduction (1-2 sentences only):
Mary introduces herself:"""

    try:
        logger.info("🎬 Generating initial AI greeting for Mary...")
        response = generate_ai_response(greeting_prompt, pipe)
        if response and response.strip():
            cleaned_response = response.strip()
            cached_greeting = cleaned_response  # Cache the greeting
            logger.info(f"✅ AI greeting generated and cached: {cached_greeting[:50]}...")
            return cached_greeting
        else:
            logger.warning("⚠️ AI greeting was empty, using fallback")
    except Exception as e:
        logger.error(f"❌ AI greeting generation failed: {e}")

    fallback = f"Hello! I'm {mary['name']}, I'm {mary['age']} and recently retired. I'm interested in fitness options for my age, but I have some concerns about safety."
    cached_greeting = fallback  # Cache the fallback greeting
    logger.info(f"📝 Using fallback greeting: {fallback}")
    return fallback

def chat_with_mary(message: str, user_id: str = "default") -> str:
    """Main AI chat function for sales training"""
    start_time = time.time()
    
    try:
        # Update performance tracking
        performance_stats["total_requests"] += 1
        performance_stats["last_request_time"] = start_time
        performance_stats["ai_generations"] += 1
        
        # Create session key for conversations
        session_key = f"{user_id}_mary"
        
        # Get conversation context
        contexts = conversation_contexts.get(session_key, [])
        
        logger.info(f"🤖 Generating AI response for Mary: {message[:50]}...")
        
        # Build AI prompt
        prompt = build_mary_prompt(message, contexts)

        # Generate response using the AI model
        response = generate_ai_response(prompt, pipe)
        
        # Handle AI generation failure
        if response is None:
            performance_stats["ai_failures"] += 1
            logger.error(f"AI generation failed for Mary")
            return "I'm sorry, I need a moment to think. Could you repeat that?"
        
        # Clean up the AI response to remove any salesperson content
        cleaned_response = response.strip()
        
        # Remove "Mary:" prefix if present
        if cleaned_response.lower().startswith("mary:"):
            cleaned_response = cleaned_response[5:].strip()
        
        # Remove any "Salesperson:" content and everything after it
        if "Salesperson:" in cleaned_response:
            cleaned_response = cleaned_response.split("Salesperson:")[0].strip()
        
        # Remove any "Salesperson" content and everything after it (without colon)
        if "Salesperson" in cleaned_response:
            cleaned_response = cleaned_response.split("Salesperson")[0].strip()
        
        # Use cleaned response
        response = cleaned_response if cleaned_response else "I'm sorry, could you repeat that?"

        # Calculate timing
        ai_time = time.time() - start_time
        performance_stats["total_ai_time"] += ai_time
        performance_stats["average_ai_time"] = performance_stats["total_ai_time"] / performance_stats["ai_generations"]

        # Store conversation context
        if session_key not in conversation_contexts:
            conversation_contexts[session_key] = []
        
        conversation_entry = {
            "user": message,
            "response": response,
            "timestamp": time.time()
        }
        conversation_contexts[session_key].append(conversation_entry)

        # Limit context length
        if len(conversation_contexts[session_key]) > MAX_CONTEXT_LENGTH:
            conversation_contexts[session_key] = conversation_contexts[session_key][-MAX_CONTEXT_LENGTH:]

        # Save conversation backup after each exchange to prevent loss
        try:
            logger.debug(f"Conversation context for session {session_key}: {conversation_contexts[session_key]}")
            logger.debug("Attempting to save conversation backup...")
            save_conversation_backup()
        except Exception as backup_error:
            logger.warning(f"⚠️ Backup save failed but continuing: {backup_error}")

        # Update performance stats
        total_time = time.time() - start_time
        performance_stats["total_response_time"] += total_time
        performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
        
        logger.info(f"✨ AI response for Mary generated ({total_time:.3f}s) - Conversation saved")
        return response
        
    except Exception as e:
        # Enhanced error handling with conversation preservation
        performance_stats["ai_failures"] += 1
        logger.error(f"❌ Error in chat_with_mary: {e}")
        
        # Still save the user message even if AI fails
        try:
            if session_key not in conversation_contexts:
                conversation_contexts[session_key] = []
            conversation_contexts[session_key].append({
                "user": message,
                "response": "I'm having trouble right now. Could you try asking that again?",
                "timestamp": time.time(),
                "error": True
            })
            save_conversation_backup()
            logger.info("💾 User message saved despite AI error")
        except Exception as backup_error:
            logger.error(f"❌ Failed to save conversation after error: {backup_error}")
        
        return "I'm having trouble right now. Could you try asking that again?"

# API Endpoints

# Web Interface Endpoint
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page that renders the chat.html template with Mary's greeting"""
    return templates.TemplateResponse(
        "chat.html", 
        {
            "request": request, 
            "initial_greeting": get_initial_greeting(),
            "character_name": CHARACTER_PROFILE["name"]
        }
    )

# Main Chat API Endpoints
@app.post("/api/chat")
async def api_chat(payload: dict):
    """Main chat endpoint for sales training conversations"""
    message = payload.get("message", "")
    user_id = payload.get("user_id", "default")
    
    response = chat_with_mary(message, user_id)
    session_key = f"{user_id}_mary"
    
    return {
        "response": response, 
        "status": "success",
        "user_id": user_id,
        "character": {
            "name": CHARACTER_PROFILE["name"],
            "age": CHARACTER_PROFILE["age"],
            "status": CHARACTER_PROFILE["status"],
            "description": f"{CHARACTER_PROFILE['name']}, {CHARACTER_PROFILE['age']}-year-old {CHARACTER_PROFILE['status']}"
        },
        "context_size": len(conversation_contexts.get(session_key, []))
    }

# Utility Endpoints
@app.get("/api/greeting")
async def api_greeting():
    """Get Mary's initial greeting"""
    return {
        "greeting": get_initial_greeting(),
        "character": {"name": CHARACTER_PROFILE["name"], "age": CHARACTER_PROFILE["age"], "status": CHARACTER_PROFILE["status"]}
    }

@app.get("/api/character")
async def get_character_details():
    """Get Mary's character profile"""
    return {"character": CHARACTER_PROFILE}

@app.post("/chat")
async def chat(request: dict):
    """Legacy chat endpoint"""
    message = request.get("message", "")
    user_id = request.get("user_id", "default")
    return {"response": chat_with_mary(message, user_id)}

# Session Management Endpoints
@app.post("/api/reset-conversation")
async def reset_conversation(payload: dict):
    """Reset conversation for fresh training session"""
    user_id = payload.get("user_id", "default")
    session_key = f"{user_id}_mary"
    
    if session_key in conversation_contexts:
        context_count = len(conversation_contexts[session_key])
        del conversation_contexts[session_key]
        save_conversation_backup()  # Save after reset
        logger.info(f"🗑️ Reset conversation - {context_count} entries")
        return {"status": "conversation reset", "user_id": user_id, "cleared_entries": context_count}
    return {"status": "no conversation found", "user_id": user_id}

@app.get("/api/conversation/{user_id}")
async def get_conversation_history(user_id: str):
    """Get conversation history for a user"""
    session_key = f"{user_id}_mary"
    contexts = conversation_contexts.get(session_key, [])
    
    return {
        "user_id": user_id,
        "conversation_count": len(contexts),
        "conversation": contexts,
        "last_activity": contexts[-1]["timestamp"] if contexts else None
    }

# Monitoring & Analytics

@app.get("/health")
async def health():
    """Health check endpoint with comprehensive performance metrics"""
    # Basic stats
    active_sessions = len(conversation_contexts)
    total_context_entries = sum(len(contexts) for contexts in conversation_contexts.values())
    uptime = time.time() - performance_stats["startup_time"]
    
    # Performance calculations
    total_requests = performance_stats["total_requests"]
    ai_generation_rate = (performance_stats["ai_generations"] / max(total_requests, 1)) * 100
    
    # Speed predictions based on current stats
    predicted_times = {
        "ai_generation": f"{performance_stats['average_ai_time']:.2f}s" if performance_stats['average_ai_time'] > 0 else "2-8s"
    }
    
    # Request rate (requests per minute)
    requests_per_minute = (total_requests / max(uptime / 60, 1)) if uptime > 60 else 0
    
    return {
        "status": "ok",
        "uptime_seconds": round(uptime, 2),
        "model": model_name,
        "system_type": "Pure AI Sales Training System",
        
        # Character info
        "character": {
            "name": CHARACTER_PROFILE["name"],
            "age": CHARACTER_PROFILE["age"],
            "status": CHARACTER_PROFILE["status"]
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
            "ai_generations": {
                "count": performance_stats["ai_generations"],
                "percentage": round(ai_generation_rate, 1)
            }
        },
        
        # Speed predictions
        "predicted_response_times": predicted_times,
        
        # Memory usage info
        "memory_usage": {
            "active_sessions": active_sessions,
            "total_context_entries": total_context_entries,
            "max_context_length": MAX_CONTEXT_LENGTH
        },
        
        # System capabilities
        "features": [
            "ai_driven_responses",
            "context_memory",
            "sales_training_roleplay",
            "character_consistency",
            "trainable_ai_system"
        ],
        
        # Failure statistics
        "reliability_stats": {
            "ai_failures": performance_stats["ai_failures"],
            "failure_rate": round((performance_stats["ai_failures"] / max(total_requests, 1)) * 100, 2)
        },
        
        # Performance recommendations
        "recommendations": {
            "overall_performance": "optimized" if performance_stats["average_response_time"] < 2.0 else "moderate" if performance_stats["average_response_time"] < 5.0 else "slow",
            "reliability": "excellent" if performance_stats["ai_failures"] == 0 else "good" if performance_stats["ai_failures"] < 5 else "needs_attention",
            "ai_training": "Pure AI system - all responses generated dynamically for realistic sales training"
        }
    }

@app.get("/api/conversation-stats")
async def conversation_stats():
    """Get conversation statistics for training analysis"""
    stats = {}
    mary_stats = {
        "total_sessions": 0,
        "total_exchanges": 0,
        "unique_users": set(),
        "last_used": None
    }
    
    for session_key, contexts in conversation_contexts.items():
        # Parse session key to get user
        if "_" in session_key:
            user_id, _ = session_key.rsplit("_", 1)
        else:
            user_id = session_key
        
        # User stats
        if user_id not in stats:
            stats[user_id] = {
                "total_conversations": 0,
                "total_exchanges": 0,
                "last_activity": None
            }
        
        stats[user_id]["total_conversations"] += 1
        stats[user_id]["total_exchanges"] += len(contexts)
        
        latest_activity = max([ctx["timestamp"] for ctx in contexts]) if contexts else None
        if not stats[user_id]["last_activity"] or (latest_activity and latest_activity > stats[user_id]["last_activity"]):
            stats[user_id]["last_activity"] = latest_activity
        
        # Mary stats
        mary_stats["total_sessions"] += 1
        mary_stats["total_exchanges"] += len(contexts)
        mary_stats["unique_users"].add(user_id)
        
        if not mary_stats["last_used"] or (latest_activity and latest_activity > mary_stats["last_used"]):
            mary_stats["last_used"] = latest_activity
    
    # Convert set to count for JSON serialization
    mary_stats["unique_users"] = len(mary_stats["unique_users"])
    
    return {
        "active_conversations": len(conversation_contexts),
        "unique_users": len(stats),
        "user_stats": stats,
        "mary_stats": mary_stats,
        "system_type": "Pure AI Sales Training System"
    }

# Add endpoint to toggle fallback responses
@app.post("/api/toggle-fallback")
async def api_toggle_fallback(payload: dict):
    """Toggle fallback responses on or off."""
    enable = payload.get("enable", True)
    toggle_fallback_responses(enable)
    return {"status": "success", "fallback_responses_enabled": enable}

# Graceful shutdown handler
import signal
import atexit

def graceful_shutdown(signum=None, frame=None):
    """Save conversations before shutdown"""
    logger.info("🛑 Graceful shutdown initiated - saving conversations...")
    try:
        save_conversation_backup()
        logger.info("💾 Conversations saved successfully")
    except Exception as e:
        logger.error(f"❌ Failed to save conversations during shutdown: {e}")

# Register shutdown handlers
signal.signal(signal.SIGINT, graceful_shutdown)
signal.signal(signal.SIGTERM, graceful_shutdown)
atexit.register(graceful_shutdown)

if __name__ == "__main__":
    try:
        logger.info("🚀 Starting AI Sales Training Chatbot with conversation persistence...")
        uvicorn.run(app, host="0.0.0.0", port=8000)  
    except KeyboardInterrupt:
        logger.info("🔄 Received shutdown signal")
        graceful_shutdown()
    except Exception as e:
        logger.error(f"❌ Application error: {e}")
        graceful_shutdown()
        raise

# To run the app: python src/fitness_chatbot.py
# or uvicorn src.fitness_chatbot:app --host 0.0.0.0 --port 8000 --reload
