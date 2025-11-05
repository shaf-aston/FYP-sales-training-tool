"""
Web interface routes for serving HTML templates
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from services.chat_service import chat_service
from services.model_service import model_service
from models.character_profiles import get_mary_profile
from infrastructure.settings import TEMPLATES_DIR

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
  """Home page that renders the chat.html template with Mary's greeting"""
  pipe = model_service.get_pipeline()
  initial_greeting = chat_service.get_initial_greeting(pipe)
  character = get_mary_profile()
  
  return templates.TemplateResponse(
    "chat.html", 
    {
      "request": request, 
      "initial_greeting": initial_greeting,
      "character_name": character["name"]
    }
  )

@router.post("/chat")
async def legacy_chat_endpoint(request: dict):
  """Legacy chat endpoint for backwards compatibility"""
  from fastapi import HTTPException
  
  message = request.get("message", "")
  user_id = request.get("user_id", "default")
  
  if not message:
    raise HTTPException(status_code=400, detail="Message is required")
  
  pipe = model_service.get_pipeline()
  result = chat_service.chat_with_mary(message, user_id, pipe)
  
  return {"response": result}