"""
Simple test server to verify FastAPI setup
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
src_dir = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Test Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

@app.get("/")
async def root():
    return {"message": "Test server is running!"}

@app.get("/api/v2/personas")
async def get_personas():
    return {
        "personas": [
            {
                "name": "Mary",
                "description": "Professional sales manager with 10+ years experience",
                "personality_traits": ["Professional", "Direct", "Results-Oriented"],
                "communication_style": "Professional Communication",
            }
        ],
        "total_count": 1
    }

@app.post("/api/v2/progress/initialize")
async def initialize_progress(user_id: str = "demo_user_123"):
    return {
        "profile_created": True,
        "user_profile": {
            "user_id": user_id,
            "total_sessions": 0,
            "total_training_hours": 0.0,
            "experience_level": "beginner"
        }
    }

@app.get("/api/v2/progress/{user_id}/dashboard")
async def get_dashboard_data(user_id: str):
    return {
        "user_profile": {"user_id": user_id, "experience_level": "beginner"},
        "overall_progress": {"completion_percentage": 0},
        "skills_breakdown": {},
        "session_statistics": {
            "total_sessions": 0,
            "total_hours": 0.0,
            "average_session_length": 0,
            "sessions_this_week": 0,
            "average_success_rating": 0
        },
        "recent_performance": [],
        "active_goals": [],
        "next_recommendations": [],
        "achievements_summary": {"total_badges": 0, "recent_achievements": []}
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting test server...")
    print("🌐 Server will be available at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)