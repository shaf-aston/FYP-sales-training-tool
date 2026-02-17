import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/web')))

import pytest
from web.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test_secret_key'
    return app.test_client()

def test_api_health(client):
    response = client.get('/api/health')
    assert response.status_code == 200
    assert "ok" in response.json
    assert "active" in response.json
    assert "available_providers" in response.json
    assert "performance_stats" in response.json

def test_chat(client):
    # Initialize session first
    init_response = client.post('/api/init')
    assert init_response.status_code == 200
    session_id = init_response.json.get('session_id')
    
    # Send chat message with session ID in header
    response = client.post('/api/chat', 
        json={"message": "Hello", "provider": "groq"},
        headers={'X-Session-ID': session_id}
    )
    assert response.status_code == 200
    assert "success" in response.json or "message" in response.json