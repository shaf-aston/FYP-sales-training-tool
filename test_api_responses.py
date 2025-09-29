#!/usr/bin/env python3
"""
Test script to verify the improved quick response patterns work with the live API
"""
import requests
import json

def test_api_chat(message, character_type="mary_senior"):
    """Test the chat API with a message"""
    url = "http://localhost:8000/api/chat"
    payload = {
        "message": message,
        "user_id": "test_user",
        "character_type": character_type
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Message: '{message}'")
            print(f"📝 Response: {data['response']}")
            print(f"👤 Character: {data['character']['name']}")
            print("-" * 50)
            return data
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    print("🧪 Testing improved quick response patterns via API")
    print("=" * 60)
    
    # Test the previously problematic messages
    test_messages = [
        "hey, what do you like to eat?",  # Should get food response, not greeting
        "hi there",                       # Should get greeting
        "hello",                          # Should get greeting  
        "what about your knees?",         # Should get knee response
        "help me with my workout",        # Should use AI generation
        "what's your exercise history?",  # Should get exercise history response
    ]
    
    for message in test_messages:
        test_api_chat(message)
    
    print("\n✨ API testing complete!")