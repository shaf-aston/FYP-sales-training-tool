"""
Chat service for handling conversations and AI interactions
Enhanced with integrated context management, prompt optimization, and analytics
"""
import time
import logging
from typing import Dict, List, Optional
import uuid

from models.character_profiles import get_mary_profile, build_mary_prompt, PERSONAS
from config.settings import MAX_CONTEXT_LENGTH, PERFORMANCE_STATS

# Import enhanced_responses - handle path issues
try:
  from fallback_responses import generate_ai_response, get_fallback
except ImportError:
  import sys
  from pathlib import Path
  src_path = str(Path(__file__).resolve().parent.parent)
  if src_path not in sys.path:
    sys.path.insert(0, src_path)
  from fallback_responses import generate_ai_response, get_fallback

# Import new integrated services
from .context_service import get_context_manager
from .prompt_service import get_prompt_manager
from .analytics_service import get_analytics_aggregator
from .feedback_service import feedback_service
from .persona_service import persona_service

logger = logging.getLogger(__name__)

class ChatService:
  """Enhanced service for managing chat conversations and AI interactions"""
  
  def __init__(self):
    self.conversation_contexts: Dict[str, List[dict]] = {}
    self.performance_stats = PERFORMANCE_STATS.copy()
    self.performance_stats["startup_time"] = time.time()
    
    # Initialize integrated services
    self.context_manager = get_context_manager()
    self.prompt_manager = get_prompt_manager()
    self.analytics = get_analytics_aggregator()
    
    # Session management
    self.active_sessions: Dict[str, Dict] = {}
    
    logger.info("🔧 ChatService initialized with enhanced services")
  
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

  # Backwards-compatible fallback helper expected by tests
  def _get_fallback_response(self, message: str) -> str:
    """Return a safe fallback response when AI generation is unavailable.

    This mirrors legacy behavior expected by tests and callers that use a
    private fallback helper. It intentionally ignores the input message and
    returns a generic but friendly response.
    """
    try:
      return get_fallback()
    except Exception:
      # Final safety net
      return "I'm sorry, I need a moment. Could you repeat that in a simpler way?"
  
  def chat_with_persona(self, message: str, user_id: str, persona_name: str, pipe, session_id: str = None) -> Dict:
    """Enhanced AI chat function with integrated services"""
    start_time = time.time()
    
    # Generate session ID if not provided
    if not session_id:
      session_id = str(uuid.uuid4())
    
    try:
      # Track analytics event
      self.analytics.track_event(user_id, session_id, "message_sent", {
        "message": message,
        "persona_name": persona_name,
        "message_length": len(message),
        "response_time_seconds": 0
      })
      
      # Update performance tracking
      self.performance_stats["total_requests"] += 1
      self.performance_stats["last_request_time"] = start_time
      self.performance_stats["ai_generations"] += 1
      
      # Get or create session
      session_key = f"{user_id}_{persona_name}_{session_id}"
      if session_key not in self.active_sessions:
        self.active_sessions[session_key] = {
          "user_id": user_id,
          "persona_name": persona_name,
          "session_id": session_id,
          "start_time": start_time,
          "messages": [],
          "context_added": False
        }
        
        # Track session start
        self.analytics.track_event(user_id, session_id, "session_start", {
          "persona_name": persona_name,
          "start_time": start_time
        })
      
      session = self.active_sessions[session_key]
      
      # Add user message to context manager
      self.context_manager.add_context(
        message, 
        role="user", 
        importance=0.8, 
        message_type="message",
        session_id=session_id
      )
      
      # Add persona context if not already added
      if not session["context_added"]:
        persona_data = PERSONAS.get(persona_name, {})
        persona_description = f"You are {persona_data.get('name', persona_name)}, {persona_data.get('description', 'a sales training persona')}"
        self.context_manager.add_persona_context(persona_description, session_id)
        session["context_added"] = True
      
      # Get session data for prompt building
      session_data = {
        "objectives": ["Build rapport", "Practice sales skills", "Handle objections"],
        "scenario": f"Sales training with {persona_name}",
        "focus_areas": ["Communication", "Persuasion", "Empathy"]
      }
      
      logger.info(f"🤖 Generating AI response for {persona_name}: {message[:50]}...")
      
      # Build optimized prompt using prompt manager
      prompt = self.prompt_manager.build_sales_training_prompt(
        user_input=message,
        persona_name=persona_name,
        session_data=session_data,
        session_id=session_id
      )
      
      # Generate response using the AI model
      response = generate_ai_response(prompt, pipe)
      
      # Handle AI generation failure
      if response is None:
        self.performance_stats["ai_failures"] += 1
        logger.error(f"AI generation failed for {persona_name}")
        return {
          "response": "I'm sorry, I need a moment to think. Could you repeat that?",
          "status": "error",
          "session_id": session_id,
          "persona_name": persona_name
        }

      # Add assistant response to context
      self.context_manager.add_context(
        response,
        role="assistant",
        importance=0.7,
        message_type="message",
        session_id=session_id
      )

      # Store in session
      session["messages"].append({
        "user_message": message,
        "persona_response": response,
        "timestamp": time.time()
      })

      # Calculate timing
      response_time = time.time() - start_time
      ai_time = response_time  # Simplified for now
      
      self.performance_stats["total_ai_time"] += ai_time
      self.performance_stats["average_ai_time"] = self.performance_stats["total_ai_time"] / self.performance_stats["ai_generations"]

      # Update performance stats
      self.performance_stats["total_response_time"] += response_time
      self.performance_stats["average_response_time"] = self.performance_stats["total_response_time"] / self.performance_stats["total_requests"]
      
      # Update analytics with response time
      self.analytics.track_event(user_id, session_id, "message_sent", {
        "message": message,
        "persona_name": persona_name,
        "message_length": len(message),
        "response_time_seconds": response_time,
        "response_length": len(response)
      })
      
      logger.info(f"✨ AI response for {persona_name} generated ({response_time:.3f}s)")
      
      return {
        "response": response,
        "status": "success",
        "session_id": session_id,
        "persona_name": persona_name,
        "response_time": round(response_time, 3),
        "message_count": len(session["messages"]),
        "context_tokens": self.context_manager.get_total_tokens()
      }
      
    except Exception as e:
      # Enhanced error handling
      self.performance_stats["ai_failures"] += 1
      logger.error(f"❌ Error in chat_with_persona: {e}")
      
      # Track error event
      self.analytics.track_event(user_id, session_id or "unknown", "error", {
        "error_message": str(e),
        "persona_name": persona_name
      })
      
      return {
        "response": "I'm having trouble right now. Could you try asking that again?",
        "status": "error",
        "error": str(e),
        "session_id": session_id,
        "persona_name": persona_name
      }
  
  def chat_with_mary(self, message: str, user_id: str, pipe) -> str:
    """Legacy Mary chat function - now uses enhanced system"""
    result = self.chat_with_persona(message, user_id, "Mary", pipe)
    return result.get("response", "Error occurred")
  
  def end_session(self, user_id: str, session_id: str, persona_name: str = None) -> Dict:
    """End training session and generate feedback"""
    session_key = f"{user_id}_{persona_name}_{session_id}" if persona_name else None
    
    # Find session if key not exact
    if not session_key or session_key not in self.active_sessions:
      for key, session in self.active_sessions.items():
        if session["user_id"] == user_id and session["session_id"] == session_id:
          session_key = key
          break
    
    if not session_key or session_key not in self.active_sessions:
      return {"status": "session not found", "user_id": user_id, "session_id": session_id}
    
    session = self.active_sessions[session_key]
    end_time = time.time()
    duration = (end_time - session["start_time"]) / 60  # Convert to minutes
    
    try:
      # Generate feedback if there were messages
      feedback_report = None
      if session["messages"]:
        conversation_data = {
          "session_id": session_id,
          "messages": []
        }
        
        # Convert messages to feedback format
        for msg in session["messages"]:
          conversation_data["messages"].extend([
            {"role": "user", "content": msg["user_message"]},
            {"role": "assistant", "content": msg["persona_response"]}
          ])
        
        # Generate feedback
        feedback_generator = feedback_service
        feedback_report = feedback_generator.analyze_conversation(
          conversation_data, user_id
        )
      
      # Track session end analytics
      session_data = {
        "session_id": session_id,
        "user_id": user_id,
        "persona_name": session["persona_name"],
        "start_time": session["start_time"],
        "end_time": end_time,
        "duration_minutes": duration,
        "messages_exchanged": len(session["messages"]),
        "completion_status": "completed"
      }
      
      if feedback_report:
        session_data["overall_score"] = feedback_report.get("overall_scores", {}).get("weighted_average", 0)
        session_data["category_scores"] = feedback_report.get("overall_scores", {})
        session_data["feedback_items"] = feedback_report.get("feedback_items", [])
      
      # Track analytics
      self.analytics.track_event(user_id, session_id, "session_end", session_data)
      
      # Clear session context
      self.context_manager.clear_session_context(session_id)
      
      # Remove from active sessions
      del self.active_sessions[session_key]
      
      logger.info(f"🏁 Session ended: {session_id} ({duration:.1f} min, {len(session['messages'])} messages)")
      
      return {
        "status": "session ended",
        "session_id": session_id,
        "duration_minutes": round(duration, 1),
        "messages_exchanged": len(session["messages"]),
        "feedback_report": feedback_report,
        "analytics_tracked": True
      }
      
    except Exception as e:
      logger.error(f"Error ending session {session_id}: {e}")
      return {
        "status": "error ending session",
        "session_id": session_id,
        "error": str(e)
      }
  
  def reset_conversation(self, user_id: str) -> dict:
    """Reset conversation for fresh training session - legacy method"""
    session_key = f"{user_id}_mary"
    
    # Clear legacy contexts
    if session_key in self.conversation_contexts:
      context_count = len(self.conversation_contexts[session_key])
      del self.conversation_contexts[session_key]
      logger.info(f"🗑️ Reset legacy conversation - {context_count} entries")
      return {"status": "conversation reset", "user_id": user_id, "cleared_entries": context_count}
    
    # Clear active sessions for user
    sessions_cleared = 0
    keys_to_remove = []
    for key, session in self.active_sessions.items():
      if session["user_id"] == user_id:
        keys_to_remove.append(key)
        sessions_cleared += 1
    
    for key in keys_to_remove:
      del self.active_sessions[key]
    
    if sessions_cleared > 0:
      logger.info(f"🗑️ Reset {sessions_cleared} active sessions for user {user_id}")
      return {"status": "sessions reset", "user_id": user_id, "sessions_cleared": sessions_cleared}
    
    return {"status": "no sessions found", "user_id": user_id}
  
  def get_session_feedback(self, user_id: str, session_id: str) -> Dict:
    """Get detailed feedback for a session"""
    try:
      # Check if session is still active
      session_key = None
      for key, session in self.active_sessions.items():
        if session["user_id"] == user_id and session["session_id"] == session_id:
          session_key = key
          break
      
      if session_key:
        session = self.active_sessions[session_key]
        
        if not session["messages"]:
          return {"status": "no messages", "message": "Session has no conversation data"}
        
        # Build conversation data for feedback
        conversation_data = {
          "session_id": session_id,
          "messages": []
        }
        
        for msg in session["messages"]:
          conversation_data["messages"].extend([
            {"role": "user", "content": msg["user_message"]},
            {"role": "assistant", "content": msg["persona_response"]}
          ])
        
        # Generate feedback
        feedback_report = feedback_service.analyze_conversation(conversation_data, user_id)
        
        return {
          "status": "success",
          "session_id": session_id,
          "feedback": feedback_report,
          "session_active": True
        }
      
      return {"status": "session not found", "session_id": session_id}
      
    except Exception as e:
      logger.error(f"Error generating session feedback: {e}")
      return {"status": "error", "error": str(e)}
  
  def get_conversation_stats(self) -> dict:
    """Get enhanced conversation statistics with analytics integration"""
    # Legacy stats for backwards compatibility
    legacy_stats = {}
    mary_stats = {
      "total_sessions": 0,
      "total_exchanges": 0,
      "unique_users": set(),
      "last_used": None
    }
    
    # Process legacy conversations
    for session_key, contexts in self.conversation_contexts.items():
      if "_" in session_key:
        user_id, _ = session_key.rsplit("_", 1)
      else:
        user_id = session_key
      
      if user_id not in legacy_stats:
        legacy_stats[user_id] = {
          "total_conversations": 0,
          "total_exchanges": 0,
          "last_activity": None
        }
      
      legacy_stats[user_id]["total_conversations"] += 1
      legacy_stats[user_id]["total_exchanges"] += len(contexts)
      
      latest_activity = max([ctx["timestamp"] for ctx in contexts]) if contexts else None
      if not legacy_stats[user_id]["last_activity"] or (latest_activity and latest_activity > legacy_stats[user_id]["last_activity"]):
        legacy_stats[user_id]["last_activity"] = latest_activity
      
      mary_stats["total_sessions"] += 1
      mary_stats["total_exchanges"] += len(contexts)
      mary_stats["unique_users"].add(user_id)
      
      if not mary_stats["last_used"] or (latest_activity and latest_activity > mary_stats["last_used"]):
        mary_stats["last_used"] = latest_activity
    
    # Enhanced stats from active sessions
    active_sessions_stats = {
      "total_active_sessions": len(self.active_sessions),
      "sessions_by_persona": {},
      "unique_active_users": len(set(s["user_id"] for s in self.active_sessions.values())),
      "average_session_duration": 0,
      "total_messages": 0
    }
    
    if self.active_sessions:
      current_time = time.time()
      total_duration = 0
      total_messages = 0
      
      for session in self.active_sessions.values():
        persona = session["persona_name"]
        if persona not in active_sessions_stats["sessions_by_persona"]:
          active_sessions_stats["sessions_by_persona"][persona] = 0
        active_sessions_stats["sessions_by_persona"][persona] += 1
        
        duration = (current_time - session["start_time"]) / 60  # minutes
        total_duration += duration
        total_messages += len(session["messages"])
      
      active_sessions_stats["average_session_duration"] = total_duration / len(self.active_sessions)
      active_sessions_stats["total_messages"] = total_messages
    
    mary_stats["unique_users"] = len(mary_stats["unique_users"])
    
    return {
      "active_conversations": len(self.conversation_contexts),
      "unique_users": len(legacy_stats),
      "user_stats": legacy_stats,
      "mary_stats": mary_stats,
      "enhanced_stats": active_sessions_stats,
      "context_manager_stats": self.context_manager.get_context_summary(),
      "system_type": "Enhanced AI Sales Training System with Analytics"
    }
  
  def get_user_analytics(self, user_id: str, days_back: int = 30) -> Dict:
    """Get comprehensive user analytics"""
    try:
      analytics = self.analytics.generate_user_analytics(user_id, days_back)
      return {
        "status": "success",
        "user_id": user_id,
        "analytics": analytics
      }
    except Exception as e:
      logger.error(f"Error getting user analytics: {e}")
      return {
        "status": "error",
        "user_id": user_id,
        "error": str(e)
      }
  
  def get_system_analytics(self, days_back: int = 7) -> Dict:
    """Get system-wide analytics"""
    try:
      analytics = self.analytics.generate_system_analytics(days_back)
      return {
        "status": "success",
        "analytics": analytics,
        "active_services": {
          "context_manager": True,
          "prompt_manager": True,
          "analytics_aggregator": True,
          "feedback_service": True
        }
      }
    except Exception as e:
      logger.error(f"Error getting system analytics: {e}")
      return {
        "status": "error",
        "error": str(e)
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