"""
Chat API routes
"""
from fastapi import APIRouter
from models.character_profiles import get_mary_profile
from services.chat_service import chat_service
from services.model_service import model_service

router = APIRouter()

@router.post("/chat")
async def api_chat(payload: dict):
  """Main chat endpoint for sales training conversations"""
  message = payload.get("message", "")
  user_id = payload.get("user_id", "default")
  
  pipe = model_service.get_pipeline()
  response = chat_service.chat_with_mary(message, user_id, pipe)
  session_key = f"{user_id}_mary"
  
  character = get_mary_profile()
  
  return {
    "response": response, 
    "status": "success",
    "user_id": user_id,
    "character": {
      "name": character["name"],
      "age": character["age"],
      "status": character["status"],
      "description": f"{character['name']}, {character['age']}-year-old {character['status']}"
    },
    "context_size": len(chat_service.conversation_contexts.get(session_key, []))
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

@router.post("/chat")
async def chat(request: dict):
  """Legacy chat endpoint"""
  message = request.get("message", "")
  user_id = request.get("user_id", "default")
  pipe = model_service.get_pipeline()
  return {"response": chat_service.chat_with_mary(message, user_id, pipe)}

@router.post("/reset-conversation")
async def reset_conversation(payload: dict):
  """Reset conversation for fresh training session"""
  user_id = payload.get("user_id", "default")
  return chat_service.reset_conversation(user_id)

@router.get("/conversation-stats")
async def conversation_stats():
  """Get conversation statistics for training analysis"""
  return chat_service.get_conversation_stats()