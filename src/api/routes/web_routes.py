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
from config.settings import TEMPLATES_DIR

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