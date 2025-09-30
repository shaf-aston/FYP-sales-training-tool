"""
System monitoring and health API routes
"""
from fastapi import APIRouter
from services.chat_service import chat_service
from services.model_service import model_service

router = APIRouter()

@router.get("/health")
async def health():
  """Health check endpoint with comprehensive performance metrics"""
  model_name = model_service.get_model_name()
  return chat_service.get_health_data(model_name)