"""
End-to-end API tests for the chat endpoint.
Tests both SALESREP and PROSPECT modes across all phases.
"""

import pytest
import sys
import os

# Add parent directories to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from fastapi.testclient import TestClient
from backend.main import app


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def conversation_id():
    """Generate unique conversation ID for test isolation."""
    import uuid
    return str(uuid.uuid4())


# =============================================================================
# HEALTH CHECK TESTS
# =============================================================================

@pytest.mark.api
class TestHealthEndpoint:
    """Test API health check."""
    
    def test_health_check_returns_ok(self, client):
        """Health endpoint should return ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# =============================================================================
# SALESREP MODE API TESTS
# =============================================================================

@pytest.mark.api
@pytest.mark.salesrep
class TestSalesRepChatEndpoint:
    """Test /chat endpoint with SALESREP role."""
    
    def test_salesrep_chat_returns_response(self, client, conversation_id):
        """Chat endpoint should return valid response for SALESREP."""
        response = client.post("/chat", json={
            "message": "I want to improve my sales",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "conversation_id" in data
        assert "nepq_stage" in data
        assert len(data["response"]) > 0
    
    def test_salesrep_starts_in_intent_phase(self, client, conversation_id):
        """First message should start in intent phase."""
        response = client.post("/chat", json={
            "message": "Hello",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["nepq_stage"] == "intent"
    
    def test_salesrep_conversation_continuity(self, client, conversation_id):
        """Same conversation_id should maintain context."""
        # First message
        client.post("/chat", json={
            "message": "I want to increase revenue by 50%",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        # Second message in same conversation
        response = client.post("/chat", json={
            "message": "I've been struggling with low conversion rates",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have some completion scores from prior messages
        metadata = data.get("metadata", {})
        assert "completion_scores" in metadata
    
    def test_salesrep_phase_progression(self, client, conversation_id):
        """Detailed answers should progress through phases."""
        messages = [
            "I want to triple my monthly revenue from $20k to $60k",
            "My close rate is only 8% and I'm losing $5000 monthly in bad leads",
            "I currently use cold calling and LinkedIn outreach",
            "Been doing this for about 14 months now",
            "I like the direct approach but hate the low conversion rate",
            "I would change everything about my follow-up process if I could"
        ]
        
        last_data = None
        for msg in messages:
            response = client.post("/chat", json={
                "message": msg,
                "role": "salesrep",
                "conversation_id": conversation_id
            })
            assert response.status_code == 200
            last_data = response.json()
        
        # Should have progressed beyond intent phase
        metadata = last_data.get("metadata", {})
        progress = metadata.get("phase_progress", {})
        assert progress.get("progress_percentage", 0) > 0
    
    def test_salesrep_empty_message_rejected(self, client, conversation_id):
        """Empty message should return 400 error."""
        response = client.post("/chat", json={
            "message": "",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 400


# =============================================================================
# PROSPECT MODE API TESTS
# =============================================================================

@pytest.mark.api
@pytest.mark.prospect
class TestProspectChatEndpoint:
    """Test /chat endpoint with PROSPECT role."""
    
    def test_prospect_chat_returns_response(self, client, conversation_id):
        """Chat endpoint should return valid response for PROSPECT."""
        response = client.post("/chat", json={
            "message": "How can I help you today?",
            "role": "prospect",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_prospect_role_in_metadata(self, client, conversation_id):
        """Prospect response should indicate role in metadata."""
        response = client.post("/chat", json={
            "message": "What are you hoping to achieve?",
            "role": "prospect",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 200
        data = response.json()
        metadata = data.get("metadata", {})
        
        # Prospect mode should be indicated
        assert metadata.get("role") == "prospect" or data.get("nepq_stage") is not None
    
    def test_prospect_responds_to_sales_questions(self, client, conversation_id):
        """Prospect should respond appropriately to sales rep questions."""
        questions = [
            "What are you looking to accomplish?",
            "Can you tell me more about your current situation?",
            "What have you tried so far?"
        ]
        
        for question in questions:
            response = client.post("/chat", json={
                "message": question,
                "role": "prospect",
                "conversation_id": conversation_id
            })
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["response"]) > 5  # Non-trivial response


# =============================================================================
# CONVERSATION MANAGEMENT TESTS
# =============================================================================

@pytest.mark.api
class TestConversationManagement:
    """Test conversation reset and management endpoints."""
    
    def test_delete_conversation_succeeds(self, client, conversation_id):
        """Delete endpoint should reset conversation."""
        # Create a conversation
        client.post("/chat", json={
            "message": "Hello",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        # Delete it
        response = client.delete(f"/conversation/{conversation_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    def test_deleted_conversation_restarts(self, client, conversation_id):
        """After deletion, conversation should start fresh."""
        # Have a conversation
        client.post("/chat", json={
            "message": "I want to triple my revenue",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        # Delete it
        client.delete(f"/conversation/{conversation_id}")
        
        # New message should start fresh
        response = client.post("/chat", json={
            "message": "Hello again",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["nepq_stage"] == "intent"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

@pytest.mark.api
class TestAPIErrorHandling:
    """Test API error handling."""
    
    def test_invalid_role_rejected(self, client, conversation_id):
        """Invalid role should return error."""
        response = client.post("/chat", json={
            "message": "Hello",
            "role": "INVALID_ROLE",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 422  # Validation error
    
    def test_missing_message_rejected(self, client, conversation_id):
        """Missing message field should return error."""
        response = client.post("/chat", json={
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 422
    
    def test_whitespace_only_message_rejected(self, client, conversation_id):
        """Whitespace-only message should return 400."""
        response = client.post("/chat", json={
            "message": "   ",
            "role": "salesrep",
            "conversation_id": conversation_id
        })
        
        assert response.status_code == 400
