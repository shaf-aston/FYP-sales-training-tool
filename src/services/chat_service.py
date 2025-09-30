"""
Chat service for handling conversations and AI interactions
"""
import time
import logging
from typing import Dict, List

from models.character_profiles import get_mary_profile, build_mary_prompt
from config.settings import MAX_CONTEXT_LENGTH, PERFORMANCE_STATS

# Import enhanced_responses - handle path issues
try:
  from enhanced_responses import generate_ai_response
except ImportError:
  import sys
  from pathlib import Path
  src_path = str(Path(__file__).resolve().parent.parent)
  if src_path not in sys.path:
    sys.path.insert(0, src_path)
  from enhanced_responses import generate_ai_response

logger = logging.getLogger(__name__)

class ChatService:
  """Service for managing chat conversations and AI interactions"""
  
  def __init__(self):
    self.conversation_contexts: Dict[str, List[dict]] = {}
    self.performance_stats = PERFORMANCE_STATS.copy()
    self.performance_stats["startup_time"] = time.time()
  
  def get_initial_greeting(self, pipe) -> str:
    """Generate Mary's initial AI greeting"""
    mary = get_mary_profile()
    greeting_prompt = f"""You are Mary, a {mary['age']}-year-old {mary['status']} meeting a fitness salesperson. Introduce yourself and express interest in getting healthier while mentioning safety concerns.\n\nMary:"""
    
    try:
      response = generate_ai_response(greeting_prompt, pipe)
      if response: 
        return response
    except Exception as e:
      logger.warning(f"AI greeting generation failed: {e}")
    
    return f"Hello! I'm {mary['name']}, interested in fitness options for my age."
  
  def chat_with_mary(self, message: str, user_id: str, pipe) -> str:
    """Main AI chat function for sales training"""
    start_time = time.time()
    
    try:
      # Update performance tracking
      self.performance_stats["total_requests"] += 1
      self.performance_stats["last_request_time"] = start_time
      self.performance_stats["ai_generations"] += 1
      
      # Create session key for conversations
      session_key = f"{user_id}_mary"
      
      # Get conversation context
      contexts = self.conversation_contexts.get(session_key, [])
      
      logger.info(f"🤖 Generating AI response for Mary: {message[:50]}...")
      
      # Build AI prompt
      prompt = build_mary_prompt(message, contexts)

      # Generate response using the AI model
      response = generate_ai_response(prompt, pipe)
      
      # Handle AI generation failure
      if response is None:
        self.performance_stats["ai_failures"] += 1
        logger.error("AI generation failed for Mary")
        return "I'm sorry, I need a moment to think. Could you repeat that?"

      # Calculate timing
      ai_time = time.time() - start_time
      self.performance_stats["total_ai_time"] += ai_time
      self.performance_stats["average_ai_time"] = self.performance_stats["total_ai_time"] / self.performance_stats["ai_generations"]

      # Store conversation context
      if session_key not in self.conversation_contexts:
        self.conversation_contexts[session_key] = []
      self.conversation_contexts[session_key].append({
        "user": message,
        "response": response,
        "timestamp": time.time()
      })

      # Limit context length
      if len(self.conversation_contexts[session_key]) > MAX_CONTEXT_LENGTH:
        self.conversation_contexts[session_key] = self.conversation_contexts[session_key][-MAX_CONTEXT_LENGTH:]

      # Update performance stats
      total_time = time.time() - start_time
      self.performance_stats["total_response_time"] += total_time
      self.performance_stats["average_response_time"] = self.performance_stats["total_response_time"] / self.performance_stats["total_requests"]
      
      logger.info(f"✨ AI response for Mary generated ({total_time:.3f}s)")
      return response
      
    except Exception as e:
      # Minimal error handling
      self.performance_stats["ai_failures"] += 1
      logger.error(f"❌ Error in chat_with_mary: {e}")
      return "I'm having trouble right now. Could you try asking that again?"
  
  def reset_conversation(self, user_id: str) -> dict:
    """Reset conversation for fresh training session"""
    session_key = f"{user_id}_mary"
    
    if session_key in self.conversation_contexts:
      context_count = len(self.conversation_contexts[session_key])
      del self.conversation_contexts[session_key]
      logger.info(f"🗑️ Reset conversation - {context_count} entries")
      return {"status": "conversation reset", "user_id": user_id, "cleared_entries": context_count}
    return {"status": "no conversation found", "user_id": user_id}
  
  def get_conversation_stats(self) -> dict:
    """Get conversation statistics for training analysis"""
    stats = {}
    mary_stats = {
      "total_sessions": 0,
      "total_exchanges": 0,
      "unique_users": set(),
      "last_used": None
    }
    
    for session_key, contexts in self.conversation_contexts.items():
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
      "active_conversations": len(self.conversation_contexts),
      "unique_users": len(stats),
      "user_stats": stats,
      "mary_stats": mary_stats,
      "system_type": "Pure AI Sales Training System"
    }
  
  def get_health_data(self, model_name: str) -> dict:
    """Get health check data with performance metrics"""
    # Basic stats
    active_sessions = len(self.conversation_contexts)
    total_context_entries = sum(len(contexts) for contexts in self.conversation_contexts.values())
    uptime = time.time() - self.performance_stats["startup_time"]
    
    # Performance calculations
    total_requests = self.performance_stats["total_requests"]
    ai_generation_rate = (self.performance_stats["ai_generations"] / max(total_requests, 1)) * 100
    
    # Speed predictions based on current stats
    predicted_times = {
      "ai_generation": f"{self.performance_stats['average_ai_time']:.2f}s" if self.performance_stats['average_ai_time'] > 0 else "2-8s"
    }
    
    # Request rate (requests per minute)
    requests_per_minute = (total_requests / max(uptime / 60, 1)) if uptime > 60 else 0
    
    from models.character_profiles import MARY_PROFILE
    
    return {
      "status": "ok",
      "uptime_seconds": round(uptime, 2),
      "model": model_name,
      "system_type": "Pure AI Sales Training System",
      
      # Character info
      "character": {
        "name": MARY_PROFILE["name"],
        "age": MARY_PROFILE["age"],
        "status": MARY_PROFILE["status"]
      },
      
      # Performance metrics
      "performance": {
        "total_requests": total_requests,
        "requests_per_minute": round(requests_per_minute, 2),
        "average_response_time": round(self.performance_stats["average_response_time"], 3),
        "average_ai_inference_time": round(self.performance_stats["average_ai_time"], 3),
        "last_request": round(time.time() - self.performance_stats["last_request_time"], 2) if self.performance_stats["last_request_time"] else None
      },
      
      # Response type distribution
      "response_distribution": {
        "ai_generations": {
          "count": self.performance_stats["ai_generations"],
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
        "ai_failures": self.performance_stats["ai_failures"],
        "failure_rate": round((self.performance_stats["ai_failures"] / max(total_requests, 1)) * 100, 2)
      },
      
      # Performance recommendations
      "recommendations": {
        "overall_performance": "optimized" if self.performance_stats["average_response_time"] < 2.0 else "moderate" if self.performance_stats["average_response_time"] < 5.0 else "slow",
        "reliability": "excellent" if self.performance_stats["ai_failures"] == 0 else "good" if self.performance_stats["ai_failures"] < 5 else "needs_attention",
        "ai_training": "Pure AI system - all responses generated dynamically for realistic sales training"
      }
    }

# Global chat service instance
chat_service = ChatService()