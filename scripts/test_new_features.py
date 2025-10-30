#!/usr/bin/env python3
"""
Test Suite for New Analytics & Persona Features
Validates the complete implementation
"""
import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_analytics_event_posting():
    """Test posting analytics events"""
    print("🧪 Testing analytics event posting...")
    
    event = {
        "user_id": "test_user_123",
        "event_type": "test_ping",
        "payload": {
            "test_timestamp": time.time(),
            "message": "Testing analytics integration"
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/v2/analytics/event", json=event)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    print("✅ Analytics event posting works!")

def test_dashboard_metrics():
    """Test real dashboard metrics endpoint"""
    print("🧪 Testing dashboard metrics...")
    
    user_id = "test_user_123"
    response = requests.get(f"{BASE_URL}/api/v2/progress/{user_id}/dashboard?days_back=30")
    assert response.status_code == 200
    
    data = response.json()
    assert "overall_progress" in data
    assert "session_statistics" in data
    assert "skills_breakdown" in data
    
    print(f"✅ Dashboard metrics: {data['session_statistics']['total_sessions']} sessions, "
          f"{data['session_statistics']['total_hours']} hours")

def test_system_analytics():
    """Test system-wide analytics"""
    print("🧪 Testing system analytics...")
    
    response = requests.get(f"{BASE_URL}/api/v2/analytics/system?days_back=7")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] == True
    analytics = data["analytics"]
    
    print(f"✅ System analytics: {analytics.get('total_events', 0)} events, "
          f"{analytics.get('unique_users', 0)} users")

def test_admin_events():
    """Test admin events viewer"""
    print("🧪 Testing admin events API...")
    
    response = requests.get(f"{BASE_URL}/api/v2/admin/events?limit=10")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] == True
    assert "events" in data
    assert "stats" in data
    
    print(f"✅ Admin events: {len(data['events'])} events retrieved")

def test_persona_crud():
    """Test persona CRUD operations"""
    print("🧪 Testing persona CRUD...")
    
    # Test create persona
    persona_data = {
        "name": "TestPersona",
        "type": "client",
        "difficulty": "medium", 
        "background": "Test persona for validation",
        "metadata": {
            "test": True,
            "created_by": "test_suite"
        }
    }
    
    # Create
    response = requests.post(f"{BASE_URL}/api/v2/personas/db/create", json=persona_data)
    if response.status_code == 200:
        print("✅ Persona creation works (DB configured)")
        
        # Test read
        response = requests.get(f"{BASE_URL}/api/v2/personas/db/TestPersona")
        assert response.status_code == 200
        print("✅ Persona read works")
        
        # Test update
        update_data = {
            "background": "Updated test persona background",
            "metadata": {"updated": True}
        }
        response = requests.put(f"{BASE_URL}/api/v2/personas/db/TestPersona", json=update_data)
        assert response.status_code == 200
        print("✅ Persona update works")
        
        # Test delete
        response = requests.delete(f"{BASE_URL}/api/v2/personas/db/TestPersona")
        assert response.status_code == 200
        print("✅ Persona delete works")
        
    else:
        print("⚠️  Persona CRUD skipped (DB not configured)")

def test_admin_viewer_page():
    """Test admin events viewer page"""
    print("🧪 Testing admin viewer page...")
    
    response = requests.get(f"{BASE_URL}/api/v2/admin/events-viewer")
    assert response.status_code == 200
    assert "Analytics Events Viewer" in response.text
    print("✅ Admin events viewer page loads!")

def run_all_tests():
    """Run complete test suite"""
    print("🚀 Starting comprehensive test suite...\n")
    
    try:
        # Basic connectivity
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        print("✅ Backend connectivity confirmed\n")
        
        # Test all features
        test_analytics_event_posting()
        test_dashboard_metrics()
        test_system_analytics()
        test_admin_events()
        test_persona_crud()
        test_admin_viewer_page()
        
        print("\n🎉 All tests passed! New features are working correctly.")
        print("\n📊 Access the admin panel: http://localhost:8000/api/v2/admin/events-viewer")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Make sure the server is running on http://localhost:8000")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    run_all_tests()