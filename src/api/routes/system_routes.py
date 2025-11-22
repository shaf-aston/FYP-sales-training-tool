"""
System monitoring and health API routes
"""
from fastapi import APIRouter
from src.services.ai_services import chat_service
from src.services.ai_services import model_service

try:
  from fallback_responses import toggle_fallback_responses
except ImportError:
  import sys
  from pathlib import Path
  src_path = str(Path(__file__).resolve().parent.parent.parent)
  if src_path not in sys.path:
    sys.path.insert(0, src_path)
  from fallback_responses import toggle_fallback_responses

router = APIRouter()

@router.get("/health")
async def health():
  """Health check endpoint with comprehensive performance metrics"""
  model_name = model_service.get_model_name()
  return chat_service.get_health_data(model_name)

@router.post("/toggle-fallback")
async def api_toggle_fallback(payload: dict):
    """Toggle fallback responses on or off."""
    enable = payload.get("enable", True)
    toggle_fallback_responses(enable)
    return {"status": "success", "fallback_responses_enabled": enable}