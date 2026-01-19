from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_logical_certainty_captures_timeline():
        response = client.post(
            "/chat",
            json={"message": "Our goal is to achieve a streamlined process and hit our sales targets. The current CRM system is frustrating and inefficient, causing delays and missed opportunities. We need a solution to improve efficiency and reduce stress.", "role": "prospect"}
        )
        assert response.status_code == 200
        assert response.json()["score"] >= 0.6  # Updated threshold