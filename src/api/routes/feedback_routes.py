"""
Feedback API Routes
Handles session analysis, feedback generation, and analytics
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
import json
from datetime import datetime, timedelta

feedback_router = APIRouter(prefix="/api/v2/feedback", tags=["Feedback"])

FEEDBACK_DATA = {
    "demo_user_123": {
        "sessions_analyzed": [],
        "overall_analytics": {
            "total_conversations": 0,
            "average_rating": 0.0,
            "improvement_areas": [],
            "strengths": []
        }
    }
}

@feedback_router.post("/analyze")
async def analyze_training_session(data: dict):
    """Analyze completed training session and generate feedback"""
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")
        success_rating = data.get("success_rating", 5)
        
        if not session_id or not user_id:
            raise HTTPException(status_code=400, detail="session_id and user_id required")
        
        analysis_result = {
            "session_id": session_id,
            "user_id": user_id,
            "analysis_timestamp": datetime.now().isoformat(),
            "success_rating": success_rating,
            "feedback_analysis": {
                "overall_scores": {
                    "communication": min(success_rating + 1, 10),
                    "persuasion": success_rating,
                    "objection_handling": max(success_rating - 1, 1),
                    "closing_ability": success_rating
                },
                "feedback_items": [
                    {
                        "title": "Communication Style",
                        "feedback_type": "positive" if success_rating > 6 else "improvement",
                        "description": "Your communication was clear and professional" if success_rating > 6 else "Focus on clearer communication",
                        "specific_example": "Good use of open-ended questions",
                        "improvement_suggestion": "Continue using active listening techniques",
                        "confidence_score": 0.85
                    },
                    {
                        "title": "Objection Handling", 
                        "feedback_type": "improvement" if success_rating < 7 else "positive",
                        "description": "Room for improvement in handling customer objections" if success_rating < 7 else "Excellent objection handling",
                        "specific_example": "Could have acknowledged concerns more effectively",
                        "improvement_suggestion": "Practice the feel-felt-found technique",
                        "confidence_score": 0.78
                    }
                ]
            },
            "recommendations": {
                "immediate_focus": [
                    {
                        "area": "objection_handling",
                        "recommendations": ["Practice common objections", "Learn reframe techniques"]
                    },
                    {
                        "area": "closing_techniques", 
                        "recommendations": ["Work on trial closes", "Practice assumptive closing"]
                    }
                ]
            }
        }
        
        if user_id not in FEEDBACK_DATA:
            FEEDBACK_DATA[user_id] = {"sessions_analyzed": [], "overall_analytics": {}}
        
        FEEDBACK_DATA[user_id]["sessions_analyzed"].append(analysis_result)
        
        return analysis_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze session: {str(e)}")

@feedback_router.get("/analytics/dashboard")
async def get_feedback_analytics(user_id: str):
    """Get dashboard analytics for user feedback"""
    try:
        user_data = FEEDBACK_DATA.get(user_id, {"sessions_analyzed": []})
        sessions = user_data["sessions_analyzed"]
        
        if not sessions:
            return {
                "user_id": user_id,
                "total_sessions": 0,
                "analytics": {
                    "average_scores": {},
                    "improvement_trends": [],
                    "top_strengths": [],
                    "focus_areas": []
                },
                "message": "No feedback data available yet"
            }
        
        total_sessions = len(sessions)
        avg_communication = sum(s["feedback_analysis"]["overall_scores"]["communication"] for s in sessions) / total_sessions
        avg_persuasion = sum(s["feedback_analysis"]["overall_scores"]["persuasion"] for s in sessions) / total_sessions
        avg_objection = sum(s["feedback_analysis"]["overall_scores"]["objection_handling"] for s in sessions) / total_sessions
        avg_closing = sum(s["feedback_analysis"]["overall_scores"]["closing_ability"] for s in sessions) / total_sessions
        
        analytics_result = {
            "user_id": user_id,
            "total_sessions": total_sessions,
            "analytics": {
                "average_scores": {
                    "communication": round(avg_communication, 1),
                    "persuasion": round(avg_persuasion, 1),
                    "objection_handling": round(avg_objection, 1),
                    "closing_ability": round(avg_closing, 1)
                },
                "improvement_trends": [
                    {"skill": "communication", "trend": "improving", "change": "+15%"},
                    {"skill": "objection_handling", "trend": "stable", "change": "0%"}
                ],
                "top_strengths": ["Active Listening", "Professional Tone"],
                "focus_areas": ["Objection Handling", "Closing Techniques"]
            },
            "last_updated": datetime.now().isoformat()
        }
        
        return analytics_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")

@feedback_router.get("/session/{session_id}/feedback")
async def get_session_feedback(session_id: str):
    """Get detailed feedback for specific session"""
    try:
        for user_id, user_data in FEEDBACK_DATA.items():
            for analysis in user_data["sessions_analyzed"]:
                if analysis["session_id"] == session_id:
                    return analysis
        
        raise HTTPException(status_code=404, detail="Session feedback not found")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get feedback: {str(e)}")

@feedback_router.get("/history/{user_id}")
async def get_feedback_history(user_id: str, limit: int = 10):
    """Get user's feedback history"""
    try:
        user_data = FEEDBACK_DATA.get(user_id, {"sessions_analyzed": []})
        sessions = user_data["sessions_analyzed"]
        
        recent_sessions = sorted(sessions, key=lambda x: x["analysis_timestamp"], reverse=True)[:limit]
        
        return {
            "user_id": user_id,
            "total_sessions": len(sessions),
            "recent_feedback": recent_sessions,
            "showing": len(recent_sessions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")