"""
Dashboard and progress API routes for frontend integration
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging
from src.data_access.character_profiles import PERSONAS

logger = logging.getLogger(__name__)

router = APIRouter()

# Mock progress data for demonstration and testing
SAMPLE_PROGRESS = {
    "user_stats": {
        "total_sessions": 5,
        "completed_scenarios": 3,
        "success_rate": 0.75,
        "average_confidence": 0.82,
        "improvement_trend": "upward"
    },
    "recent_sessions": [
        {"session_id": "session_1", "score": 85, "scenario": "initial_consultation", "date": "2025-11-10"},
        {"session_id": "session_2", "score": 78, "scenario": "membership_upgrade", "date": "2025-11-12"},
        {"session_id": "session_3", "score": 90, "scenario": "family_fitness", "date": "2025-11-14"}
    ],
    "skills_breakdown": {
        "communication": 80,
        "product_knowledge": 75,
        "objection_handling": 70,
        "closing_techniques": 85,
        "relationship_building": 88
    },
    "weekly_progress": [70, 75, 80, 85, 90]
}

# PERSONAS = [] #TODO Insert personas from character_profiles.py
PERSONAS = PERSONAS
  

@router.get("/api/v2/personas")
async def get_personas():
    """Get available training personas"""
    logger.info("Fetching available personas")
    if not PERSONAS:
        raise HTTPException(status_code=404, detail="No personas available")
    return {"personas": PERSONAS}

@router.get("/api/personas")
async def get_personas_v1():
    if not PERSONAS:
        raise HTTPException(status_code=404, detail="No personas available")
    return {"personas": PERSONAS}

@router.get("/api/v2/progress/initialize")
async def initialize_progress(user_id: str = "demo_user_123"):
    """Initialize user progress tracking"""
    logger.info(f"Initializing progress for user: {user_id}")
    
    return {
        "user_id": user_id,
        "status": "initialized",
        "message": "Progress tracking initialized successfully",
        "initial_data": SAMPLE_PROGRESS
    }

@router.get("/api/progress/initialize")
async def initialize_progress_v1(user_id: str = "demo_user_123"):
    return await initialize_progress(user_id)

@router.get("/api/v2/progress/{user_id}/dashboard")
async def get_dashboard_data(user_id: str):
    """Get comprehensive dashboard data for user"""
    logger.info(f"Fetching dashboard data for user: {user_id}")
    
    if user_id != "demo_user_123":
        empty_progress = {
            "user_stats": {
                "total_sessions": 0,
                "completed_scenarios": 0,
                "success_rate": 0,
                "average_confidence": 0,
                "improvement_trend": "starting"
            },
            "recent_sessions": [],
            "skills_breakdown": {
                "communication": 0,
                "product_knowledge": 0,
                "objection_handling": 0,
                "closing_techniques": 0,
                "relationship_building": 0
            },
            "weekly_progress": []
        }
        return empty_progress
    
    return SAMPLE_PROGRESS

@router.get("/api/progress/{user_id}/dashboard")
async def get_dashboard_data_v1(user_id: str):
    return await get_dashboard_data(user_id)

@router.post("/api/v2/progress/{user_id}/session")
async def log_training_session(user_id: str, session_data: Dict[str, Any]):
    """Log a completed training session"""
    logger.info(f"Logging session for user: {user_id}")
    
    return {
        "status": "success",
        "message": "Session logged successfully",
        "session_id": f"session_{user_id}_{len(SAMPLE_PROGRESS['recent_sessions']) + 1}"
    }

@router.get("/api/v2/scenarios")
async def get_training_scenarios():
    """Get available training scenarios"""
    scenarios = [
        {
            "id": "initial_consultation",
            "name": "Initial Consultation",
            "description": "First meeting with a potential client",
            "difficulty": "Beginner",
            "estimated_duration": "10-15 minutes"
        },
        {
            "id": "membership_upgrade",
            "name": "Membership Upgrade",
            "description": "Convincing existing member to upgrade their plan",
            "difficulty": "Intermediate",
            "estimated_duration": "15-20 minutes"
        },
        {
            "id": "objection_handling",
            "name": "Handling Price Objections",
            "description": "Dealing with cost concerns from prospects",
            "difficulty": "Advanced",
            "estimated_duration": "12-18 minutes"
        },
        {
            "id": "retention_call",
            "name": "Member Retention",
            "description": "Convincing a member not to cancel their membership",
            "difficulty": "Advanced",
            "estimated_duration": "20-25 minutes"
        }
    ]
    
    return {"scenarios": scenarios}

@router.get("/api/v2/leaderboard")
async def get_leaderboard():
    """Get training leaderboard"""
    leaderboard = [
        {"rank": 1, "name": "Alex Thompson", "score": 94.2, "sessions": 28},
        {"rank": 2, "name": "Sarah Williams", "score": 91.8, "sessions": 25},
        {"rank": 3, "name": "Demo User", "score": 85.5, "sessions": 15},
        {"rank": 4, "name": "Mike Johnson", "score": 82.1, "sessions": 22},
        {"rank": 5, "name": "Emma Davis", "score": 79.7, "sessions": 18}
    ]
    
    return {"leaderboard": leaderboard}

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Sales Roleplay Chatbot API",
        "version": "1.0.0",
        "endpoints_available": [
            "/api/v2/personas",
            "/api/v2/progress/initialize",
            "/api/v2/progress/{user_id}/dashboard",
            "/api/v2/scenarios",
            "/api/v2/leaderboard"
        ]
    }