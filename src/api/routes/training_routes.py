"""
Training API Routes
Handles training session management, progress tracking, and recommendations
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional
import json
from datetime import datetime

training_router = APIRouter(prefix="/api/v2/training", tags=["Training"])

TRAINING_DATA = {
    "demo_user_123": {
        "training_sessions": [],
        "recommendations": [
            {"area": "objection_handling", "priority": "high", "recommendations": ["Practice common objections", "Learn reframe techniques"]},
            {"area": "closing_techniques", "priority": "medium", "recommendations": ["Master assumptive close", "Trial closing practice"]},
            {"area": "rapport_building", "priority": "low", "recommendations": ["Active listening skills", "Mirroring techniques"]}
        ]
    }
}

@training_router.get("/recommendations/{user_id}")
async def get_training_recommendations(user_id: str):
    """Get personalized training recommendations for user"""
    try:
        user_data = TRAINING_DATA.get(user_id, {"recommendations": []})
        return {
            "user_id": user_id,
            "recommendations": user_data["recommendations"],
            "last_updated": datetime.now().isoformat(),
            "total_recommendations": len(user_data["recommendations"])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")

@training_router.post("/session/start")
async def start_training_session(data: dict):
    """Start a new training session"""
    try:
        user_id = data.get("user_id")
        persona_name = data.get("persona_name")
        
        if not user_id or not persona_name:
            raise HTTPException(status_code=400, detail="user_id and persona_name required")
        
        session_id = f"session_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "persona_name": persona_name,
            "start_time": datetime.now().isoformat(),
            "status": "active",
            "messages": []
        }
        
        if user_id not in TRAINING_DATA:
            TRAINING_DATA[user_id] = {"training_sessions": [], "recommendations": []}
        
        TRAINING_DATA[user_id]["training_sessions"].append(session_data)
        
        return {
            "success": True,
            "session_id": session_id,
            "message": f"Training session started with {persona_name}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@training_router.post("/session/{session_id}/message")
async def add_training_message(session_id: str, data: dict):
    """Add message to training session"""
    try:
        message = data.get("message")
        sender = data.get("sender", "user")
        
        if not message:
            raise HTTPException(status_code=400, detail="message required")
        
        session_found = False
        for user_id, user_data in TRAINING_DATA.items():
            for session in user_data["training_sessions"]:
                if session["session_id"] == session_id:
                    session["messages"].append({
                        "sender": sender,
                        "message": message,
                        "timestamp": datetime.now().isoformat()
                    })
                    session_found = True
                    break
            if session_found:
                break
        
        if not session_found:
            raise HTTPException(status_code=404, detail="Training session not found")
        
        return {
            "success": True,
            "message_count": len([msg for msg in session["messages"]])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")

@training_router.get("/session/{session_id}")
async def get_training_session(session_id: str):
    """Get training session details"""
    try:
        for user_id, user_data in TRAINING_DATA.items():
            for session in user_data["training_sessions"]:
                if session["session_id"] == session_id:
                    return session
        
        raise HTTPException(status_code=404, detail="Training session not found")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")

@training_router.get("/progress/{user_id}")
async def get_training_progress(user_id: str):
    """Get user's training progress and statistics"""
    try:
        user_data = TRAINING_DATA.get(user_id, {"training_sessions": []})
        sessions = user_data["training_sessions"]
        
        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.get("status") == "completed"])
        
        progress_data = {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": (completed_sessions / total_sessions * 100) if total_sessions > 0 else 0,
            "last_session": sessions[-1]["start_time"] if sessions else None,
            "training_hours": total_sessions * 0.5,
            "skills_progress": {
                "objection_handling": {"level": "beginner", "progress": 25},
                "closing_techniques": {"level": "beginner", "progress": 15},
                "rapport_building": {"level": "intermediate", "progress": 60}
            }
        }
        
        return progress_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")