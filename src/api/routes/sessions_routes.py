"""
Unified session management routes under /api
"""
from fastapi import APIRouter, HTTPException
from typing import Dict

from services.ai_services import chat_service
from models.request_models import SessionStartRequest, SessionEndRequest

router = APIRouter(prefix="/api", tags=["sessions"]) 

@router.post("/sessions/start")
async def start_session(request: SessionStartRequest):
    """Start a new training session and return a session_id."""
    result = chat_service.start_session(user_id=request.user_id, persona_name=request.persona_name)
    if result.get("status") != "session_started":
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to start session"))
    return result

@router.post("/sessions/end")
async def end_session(request: SessionEndRequest):
    """End an existing session and return feedback summary."""
    result = chat_service.end_session(
        user_id=request.user_id, 
        session_id=request.session_id, 
        persona_name=request.persona_name
    )
    return result
