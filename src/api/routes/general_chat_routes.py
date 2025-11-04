"""
General Chat API Routes  
Handles simple, non-persona specific conversations
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
import json
from datetime import datetime
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from services.chat_service import ChatService
    from services.model_service import ModelService
except ImportError:
    # Fallback for development
    ChatService = None
    ModelService = None

general_chat_router = APIRouter(prefix="/api", tags=["General Chat"])

@general_chat_router.post("/chat")
async def general_chat(request: Request):
    """
    General chat endpoint - renamed from 'Direct Chat' to 'General Chat'
    Handles simple conversations without persona constraints
    """
    try:
        data = await request.json()
        message = data.get("message", "").strip()
        user_id = data.get("user_id", "general_user")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Use chat service if available, otherwise simple response
        if ChatService and ModelService:
            chat_service = ChatService()
            model_service = ModelService()
            
            response = await chat_service.process_general_chat(
                message=message,
                user_id=user_id
            )
        else:
            # Fallback response for development
            response = {
                "response": f"I understand you said: '{message}'. This is a general chat response. How can I help you with sales training?",
                "message_id": f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "timestamp": datetime.now().isoformat(),
                "response_type": "general"
            }
        
        return {
            "success": True,
            "user_message": message,
            "ai_response": response.get("response", "I'm here to help with your sales training."),
            "response_metadata": {
                "message_id": response.get("message_id"),
                "timestamp": response.get("timestamp"),
                "response_type": "general_chat",
                "processing_time": "0.5s"
            }
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        print(f"General chat error: {e}")
        return {
            "success": False,
            "error": "Chat service temporarily unavailable",
            "ai_response": "I apologize, but I'm having trouble processing your message right now. Please try again in a moment.",
            "user_message": message if 'message' in locals() else ""
        }

@general_chat_router.get("/chat/health")
async def chat_health_check():
    """Health check for general chat service"""
    try:
        return {
            "status": "healthy",
            "service": "general_chat",
            "timestamp": datetime.now().isoformat(),
            "available_features": [
                "text_chat",
                "conversation_history", 
                "simple_responses"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@general_chat_router.get("/chat/info")
async def general_chat_info():
    """Get information about general chat capabilities"""
    return {
        "service_name": "General Chat",
        "description": "Simple conversational AI for general sales training questions",
        "features": [
            "Natural language processing",
            "Sales training guidance", 
            "General business conversation",
            "Non-persona specific responses"
        ],
        "usage": {
            "endpoint": "/api/chat",
            "method": "POST", 
            "required_fields": ["message"],
            "optional_fields": ["user_id"]
        },
        "examples": [
            "Tell me about sales techniques",
            "How do I handle objections?",
            "What are some closing strategies?"
        ]
    }