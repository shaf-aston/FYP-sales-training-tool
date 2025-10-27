"""
Enhanced Chat API routes with integrated services
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from models.character_profiles import get_mary_profile, PERSONAS
from services.chat_service import chat_service
from services.model_service import model_service

router = APIRouter()

@router.post("/chat")
async def api_chat(payload: dict):
  """Enhanced chat endpoint for sales training conversations"""
  message = payload.get("message", "")
  user_id = payload.get("user_id", "default")
  persona_name = payload.get("persona_name", "Mary")
  session_id = payload.get("session_id")
  
  if not message:
    raise HTTPException(status_code=400, detail="Message is required")
  
  pipe = model_service.get_pipeline()
  result = chat_service.chat_with_persona(message, user_id, persona_name, pipe, session_id)
  
  # Get persona info
  persona = PERSONAS.get(persona_name, get_mary_profile())
  
  return {
    **result,
    "character": {
      "name": persona.get("name", persona_name),
      "age": persona.get("age", "Unknown"),
      "status": persona.get("status", "Training persona"),
      "description": persona.get("description", f"{persona_name} sales training persona")
    }
  }

@router.get("/greeting")
async def api_greeting():
  """Get Mary's initial greeting"""
  pipe = model_service.get_pipeline()
  greeting = chat_service.get_initial_greeting(pipe)
  character = get_mary_profile()
  
  return {
    "greeting": greeting,
    "character": {
      "name": character["name"], 
      "age": character["age"], 
      "status": character["status"]
    }
  }

@router.get("/character")
async def get_character_details():
  """Get Mary's character profile"""
  return {"character": get_mary_profile()}

# Removed duplicate /chat route - using enhanced version above

@router.post("/reset-conversation")
async def reset_conversation(payload: dict):
  """Reset conversation for fresh training session"""
  user_id = payload.get("user_id", "default")
  return chat_service.reset_conversation(user_id)

@router.get("/conversation-stats")
async def conversation_stats():
  """Get enhanced conversation statistics for training analysis"""
  return chat_service.get_conversation_stats()

@router.post("/end-session")
async def end_session(payload: dict):
  """End training session and generate feedback"""
  user_id = payload.get("user_id", "default")
  session_id = payload.get("session_id")
  persona_name = payload.get("persona_name")
  
  if not session_id:
    raise HTTPException(status_code=400, detail="Session ID is required")
  
  return chat_service.end_session(user_id, session_id, persona_name)

@router.get("/session-feedback/{user_id}/{session_id}")
async def get_session_feedback(user_id: str, session_id: str):
  """Get detailed feedback for a training session"""
  return chat_service.get_session_feedback(user_id, session_id)

@router.get("/user-analytics/{user_id}")
async def get_user_analytics(user_id: str, days_back: int = 30):
  """Get comprehensive user analytics and progress"""
  return chat_service.get_user_analytics(user_id, days_back)

@router.get("/system-analytics")
async def get_system_analytics(days_back: int = 7):
  """Get system-wide analytics and performance metrics"""
  return chat_service.get_system_analytics(days_back)

@router.get("/personas")
async def list_personas():
  """List all available training personas"""
  return {
    "personas": [
      {
        "name": name,
        "description": persona.get("description", ""),
        "personality_traits": persona.get("personality_traits", []),
        "communication_style": persona.get("communication_style", "")
      }
      for name, persona in PERSONAS.items()
    ]
  }