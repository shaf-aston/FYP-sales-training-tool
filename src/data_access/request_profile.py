"""
Pydantic request/response models for API validation
Replaces manual validation logic with automatic type checking and validation
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoints with automatic validation"""
    message: str = Field(..., min_length=1, max_length=2000, description="User message to the persona")
    user_id: str = Field(default="api_user", pattern=r'^[a-zA-Z0-9_-]+$', description="Unique user identifier")
    persona_name: str = Field(default="Mary", description="Name of the persona to chat with")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation continuity")
    
    @validator('message')
    def validate_message_quality(cls, v):
        """Ensure message has meaningful content"""
        if len(v.strip()) < 1:
            raise ValueError("Message cannot be empty")
        return v.strip()
    
    @validator('persona_name')
    def normalize_persona_name(cls, v):
        """Normalize persona name to title case"""
        return v.strip().title()


class ChatResponse(BaseModel):
    """Response model for chat endpoints"""
    response: str = Field(..., description="Persona's response message")
    status: str = Field(default="success", description="Response status")
    session_id: Optional[str] = Field(None, description="Session identifier")
    persona_name: str = Field(..., description="Name of the responding persona")
    response_time: Optional[float] = Field(None, description="Response generation time in seconds")
    prompt_time: Optional[float] = Field(None, description="Prompt building time in seconds")
    gen_time: Optional[float] = Field(None, description="AI generation time in seconds")
    message_count: Optional[int] = Field(None, description="Number of messages in conversation")
    context_tokens: Optional[int] = Field(None, description="Number of context tokens used")
    character: Optional[Dict[str, Any]] = Field(None, description="Character information")
    analysis: Optional[Dict[str, Any]] = Field(None, description="Training analysis data")
    suggestions: Optional[List[Dict[str, str]]] = Field(None, description="Training improvement suggestions")


class SessionStartRequest(BaseModel):
    """Request to start a training session"""
    user_id: str = Field(default="demo_user_123", pattern=r'^[a-zA-Z0-9_-]+$')
    persona_name: str = Field(default="Mary", description="Persona to train with")


class SessionEndRequest(BaseModel):
    """Request to end a training session"""
    user_id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]+$')
    session_id: str = Field(..., min_length=1)
    persona_name: Optional[str] = None
    success_rating: Optional[int] = Field(None, ge=1, le=5, description="Session success rating 1-5")


class PersonaContextRequest(BaseModel):
    """Request for persona context information"""
    persona_name: str = Field(..., min_length=1, max_length=50)


class PersonaCreateRequest(BaseModel):
    """Request to create a custom persona"""
    name: str = Field(..., min_length=1, max_length=50)
    age: int = Field(..., ge=18, le=100)
    background: str = Field(..., min_length=10, max_length=500)
    personality_traits: List[str] = Field(..., min_items=1, max_items=10)
    goals: List[str] = Field(..., min_items=1, max_items=10)
    concerns: List[str] = Field(..., min_items=1, max_items=10)
    objections: List[str] = Field(..., min_items=1, max_items=10)
    budget_range: str = Field(..., min_length=3, max_length=50)
    decision_style: str = Field(..., min_length=3, max_length=100)
    expertise_level: str = Field(default="beginner")
    persona_type: str = Field(default="beginner")
    difficulty: str = Field(default="easy")
    health_considerations: Optional[List[str]] = None
    time_constraints: Optional[List[str]] = None
    preferred_communication: str = Field(default="friendly")
    industry: str = Field(default="fitness")


class FeedbackRequest(BaseModel):
    """Request model for feedback submission"""
    session_id: str = Field(..., min_length=1)
    user_id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]+$')
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = Field(None, max_length=1000)
    categories: Optional[Dict[str, int]] = Field(None, description="Category-specific ratings")


class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str
    uptime_seconds: float
    model: str
    system_type: str
    character: Dict[str, Any]
    performance: Dict[str, Any]
    response_distribution: Dict[str, Any]
    predicted_response_times: Dict[str, str]
    memory_usage: Dict[str, Any]
    features: List[str]
    reliability_stats: Dict[str, Any]
    recommendations: Dict[str, str]
