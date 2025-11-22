"""
Enhanced Chat API routes with integrated services
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from services.ai_services import persona_service
from services.ai_services.chat_service import get_chat_service, ChatService
from services.ai_services import model_service
from src.data_access.request_profile import ChatRequest, ChatResponse

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def api_chat(request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)):
  """Enhanced chat endpoint for sales training conversations"""
  
  if not request.message:
    raise HTTPException(status_code=400, detail="Message is required")
  
  pipe = await model_service.get_pipeline()
  result = chat_service.chat_with_persona(
    request.message, 
    request.user_id, 
    request.persona_name, 
    pipe, 
    request.session_id
  )
  
  p = persona_service.get_persona(request.persona_name)
  persona = {
    "name": p.name if p else request.persona_name,
    "age": p.age if p else "Unknown",
    "status": getattr(p, "expertise_level", "Training persona") if p else "Training persona",
    "description": getattr(p, "background", f"{request.persona_name} sales training persona") if p else f"{request.persona_name} sales training persona",
  }
  
  return {
    **result,
    "character": {
      "name": persona.get("name", request.persona_name),
      "age": persona.get("age", "Unknown"),
      "status": persona.get("status", "Training persona"),
      "description": persona.get("description", f"{request.persona_name} sales training persona")
    }
  }

@router.get("/greeting")
async def api_greeting(chat_service: ChatService = Depends(get_chat_service)):
  """Get Mary's initial greeting"""
  pipe = await model_service.get_pipeline()
  greeting = chat_service.get_initial_greeting(pipe)
  p = persona_service.get_persona("Mary")
  character = {"name": p.name if p else "Mary", "age": p.age if p else 65, "status": getattr(p, "expertise_level", "beginner") if p else "beginner"}
  
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
  p = persona_service.get_persona("Mary")
  if not p:
    raise HTTPException(status_code=404, detail="Mary persona not found")
  
  return {
    "character": {
      "name": p.name,
      "age": p.age,
      "background": p.background,
      "personality_traits": p.personality_traits,
      "goals": p.goals,
      "concerns": p.concerns,
      "expertise_level": p.expertise_level
    }
  }


@router.post("/reset-conversation")
async def reset_conversation(payload: dict, chat_service: ChatService = Depends(get_chat_service)):
  """Reset conversation for fresh training session"""
  user_id = payload.get("user_id", "default")
  return chat_service.reset_conversation(user_id)

@router.get("/conversation-stats")
async def conversation_stats(chat_service: ChatService = Depends(get_chat_service)):
  """Get enhanced conversation statistics for training analysis"""
  return chat_service.get_conversation_stats()

@router.post("/end-session")
async def end_session(payload: dict, chat_service: ChatService = Depends(get_chat_service)):
  """End training session and generate feedback"""
  user_id = payload.get("user_id", "default")
  session_id = payload.get("session_id")
  persona_name = payload.get("persona_name")
  
  if not session_id:
    raise HTTPException(status_code=400, detail="Session ID is required")
  
  return chat_service.end_session(user_id, session_id, persona_name)

@router.get("/session-feedback/{user_id}/{session_id}")
async def get_session_feedback(user_id: str, session_id: str, chat_service: ChatService = Depends(get_chat_service)):
  """Get detailed feedback for a training session"""
  return chat_service.get_session_feedback(user_id, session_id)

@router.get("/user-analytics/{user_id}")
async def get_user_analytics(user_id: str, days_back: int = 30, chat_service: ChatService = Depends(get_chat_service)):
  """Get comprehensive user analytics and progress"""
  return chat_service.get_user_analytics(user_id, days_back)

@router.get("/system-analytics")
async def get_system_analytics(days_back: int = 7, chat_service: ChatService = Depends(get_chat_service)):
  """Get system-wide analytics and performance metrics"""
  return chat_service.get_system_analytics(days_back)

@router.get("/personas")
async def list_personas():
  """List all available training personas"""
  return {"personas": persona_service.list_personas()}

@router.get("/personas/{persona_name}/context")
async def get_persona_context_v1(persona_name: str):
  """Unified context endpoint under /api/personas/{name}/context.
  Mirrors the richer v2 context but simplified and fast for UI needs.
  """
  p = persona_service.get_persona(persona_name)
  if not p:
    raise HTTPException(status_code=404, detail=f"Persona '{persona_name}' not found")

  persona = {
    "name": p.name,
    "age": p.age,
    "description": p.background,
    "goals": p.goals,
  }
  context = {
    "persona_info": persona,
    "conversation_style": {
      "tone": getattr(p, "preferred_communication", "friendly"),
      "personality_traits": getattr(p, "personality_traits", []),
      "main_concerns": getattr(p, "concerns", []),
      "goals": getattr(p, "goals", []),
    },
  }
  return {"success": True, "persona_name": persona_name, "context": context}