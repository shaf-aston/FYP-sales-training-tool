from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(None, description="Session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hello, I'd like to learn about your challenges.",
                "conversation_id": "abc-123"
            }
        }


class ChatResponse(BaseModel):
    response: str = Field(..., description="Bot response")
    conversation_id: Optional[str] = Field(None, description="Session ID")
    phase: Optional[str] = Field(None, description="Current phase")
    metadata: Optional[dict] = Field(None, description="Response metadata")
