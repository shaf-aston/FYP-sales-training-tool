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
from src.enhanced_responses import generate_ai_response

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

# Conversation memory system - pure AI driven
conversation_contexts = {}
MAX_CONTEXT_LENGTH = 4  # Keep last 4 exchanges per user

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
    
    # Create comprehensive prompt for AI training
    prompt = f"""You are Mary, a {mary['age']}-year-old {mary['status']} who is a potential fitness program customer. 

Character Details:
- Name: {mary['name']}
- Age: {mary['age']}, Weight: {mary['weight']}, Height: {mary['height']}
- Background: {mary['background']}
- Health Issues: {', '.join(mary['health_issues'])}
- Exercise History: {mary['exercise_history']}
- Goals: {', '.join(mary['goals'])}
- Personality: {', '.join(mary['personality'])}
- Main Concerns: {', '.join(mary['concerns'])}

Role-playing Instructions:
- You are being approached by a fitness salesperson
- Respond naturally as Mary would, showing interest but also expressing concerns
- Ask questions about safety, cost, and suitability for your age and condition
- Be friendly but cautious about making quick decisions
- Show genuine interest in improving your health
- Occasionally mention your teaching background or retirement

{conversation_history}Salesperson: {message}
Mary:"""
    
    return prompt

# The generate_ai_response function is imported from enhanced_responses.py


# Core Chat Functions

# Use MARY_PROFILE as the main character profile (defined above)
CHARACTER_PROFILE = MARY_PROFILE

def get_initial_greeting() -> str:
    """Generate Mary's initial AI greeting"""
    mary = get_mary_profile()
    greeting_prompt = f"""You are Mary, a {mary['age']}-year-old {mary['status']} meeting a fitness salesperson. Introduce yourself and express interest in getting healthier while mentioning safety concerns.\n\nMary:"""
    
    try:
        response = generate_ai_response(greeting_prompt, pipe)
        if response: return response
    except: pass
    
    return f"Hello! I'm {mary['name']}, interested in fitness options for my age."

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

        # Calculate timing
        ai_time = time.time() - start_time
        performance_stats["total_ai_time"] += ai_time
        performance_stats["average_ai_time"] = performance_stats["total_ai_time"] / performance_stats["ai_generations"]

        # Store conversation context
        if session_key not in conversation_contexts:
            conversation_contexts[session_key] = []
        conversation_contexts[session_key].append({
            "user": message,
            "response": response,
            "timestamp": time.time()
        })

        # Limit context length
        if len(conversation_contexts[session_key]) > MAX_CONTEXT_LENGTH:
            conversation_contexts[session_key] = conversation_contexts[session_key][-MAX_CONTEXT_LENGTH:]

        # Update performance stats
        total_time = time.time() - start_time
        performance_stats["total_response_time"] += total_time
        performance_stats["average_response_time"] = performance_stats["total_response_time"] / performance_stats["total_requests"]
        
        logger.info(f"✨ AI response for Mary generated ({total_time:.3f}s)")
        return response
        
    except Exception as e:
        # Minimal error handling
        performance_stats["ai_failures"] += 1
        logger.error(f"❌ Error in chat_with_mary: {e}")
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
        logger.info(f"🗑️ Reset conversation - {context_count} entries")
        return {"status": "conversation reset", "user_id": user_id, "cleared_entries": context_count}
    return {"status": "no conversation found", "user_id": user_id}

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)  

# To run the app: python src/fitness_chatbot.py
# or uvicorn src.fitness_chatbot:app --host 0.0.0.0 --port 8000 --reload
