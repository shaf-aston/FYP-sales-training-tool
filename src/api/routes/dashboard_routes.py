"""
Dashboard and progress API routes for frontend integration
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Sample personas data
PERSONAS = [
    {
        "id": "mary",
        "name": "Mary",
        "title": "New Customer",
        "description": "A 65-year-old retiree interested in starting a fitness routine",
        "personality": "Cautious but interested",
        "fitness_level": "Beginner",
        "age": 65,
        "goals": ["Weight loss", "General health", "Low impact exercises"]
    },
    {
        "id": "jake",
        "name": "Jake",
        "title": "Young Professional",
        "description": "A 28-year-old office worker looking to build muscle and stay fit",
        "personality": "Enthusiastic and goal-oriented",
        "fitness_level": "Intermediate",
        "age": 28,
        "goals": ["Muscle building", "Strength training", "Time-efficient workouts"]
    },
    {
        "id": "sarah",
        "name": "Sarah",
        "title": "Busy Parent",
        "description": "A 35-year-old mother looking for quick, effective workouts",
        "personality": "Practical and time-conscious",
        "fitness_level": "Beginner to Intermediate",
        "age": 35,
        "goals": ["Weight management", "Energy boost", "Flexible scheduling"]
    }
]

# Sample progress data
SAMPLE_PROGRESS = {
    "user_stats": {
        "total_sessions": 15,
        "completed_scenarios": 8,
        "success_rate": 75.5,
        "average_confidence": 4.2,
        "improvement_trend": "increasing"
    },
    "recent_sessions": [
        {
            "date": "2025-10-28",
            "persona": "Mary",
            "scenario": "Initial Consultation",
            "score": 85,
            "duration": "12:45",
            "key_improvements": ["Active listening", "Needs assessment"]
        },
        {
            "date": "2025-10-27",
            "persona": "Jake",
            "scenario": "Membership Upgrade",
            "score": 78,
            "duration": "15:30",
            "key_improvements": ["Objection handling", "Value proposition"]
        },
        {
            "date": "2025-10-26",
            "persona": "Sarah",
            "scenario": "Schedule Consultation",
            "score": 92,
            "duration": "10:20",
            "key_improvements": ["Time management", "Solution focus"]
        }
    ],
    "skills_breakdown": {
        "communication": 82,
        "product_knowledge": 75,
        "objection_handling": 68,
        "closing_techniques": 71,
        "relationship_building": 88
    },
    "weekly_progress": [
        {"week": "Week 1", "sessions": 3, "avg_score": 72},
        {"week": "Week 2", "sessions": 4, "avg_score": 76},
        {"week": "Week 3", "sessions": 5, "avg_score": 81},
        {"week": "Week 4", "sessions": 3, "avg_score": 85}
    ]
}

@router.get("/api/v2/personas")
async def get_personas():
    """Get available training personas"""
    logger.info("Fetching available personas")
    return {"personas": PERSONAS}

# Unified v1 equivalents under /api for frontend without /v2
@router.get("/api/personas")
async def get_personas_v1():
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
        # For other users, return default/empty data
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
    
    # In a real app, this would save to database
    # For now, just return success
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