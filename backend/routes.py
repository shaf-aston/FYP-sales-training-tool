from fastapi import HTTPException
from backend.models import ChatRequest, ChatResponse
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kalap_v2.response_generator import ResponseGenerator

# Single global instance
generator = ResponseGenerator()


def setup_routes(app):
    
    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Process chat message."""
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        session_id = request.conversation_id or str(uuid.uuid4())
        
        try:
            result = generator.generate_response(session_id, request.message)
            
            return ChatResponse(
                response=result.get("response", ""),
                conversation_id=session_id,
                phase=result.get("phase"),
                metadata=result.get("metadata", {})
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/health")
    async def health_check():
        """Health check."""
        return {"status": "ok"}
    
    @app.delete("/session/{session_id}")
    async def delete_session(session_id: str):
        """Reset session."""
        generator.context_tracker.clear_session(session_id)
        return {"status": "success"}
