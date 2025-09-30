#!/usr/bin/env python3
"""
Test script to verify the improved AI response generation works with the live API
"""
import requests
import json

def test_api_chat(message, character_type="mary_senior"):
    """Test the chat API with a message"""
    url = "http://localhost:8000/api/chat"
    payload = {
        "message": message,
        "user_id": "test_user_ai_fix",
        "character_type": character_type
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Message: '{message}'")
            print(f"📝 Response: {data['response']}")
            print(f"👤 Character: {data['character']['name']}")
            
            # Check for problematic content
            problematic_phrases = [
                "inappropriate", "insensitive", "society's norms", 
                "informational purposes", "don't use", "language that might"
            ]
            
            if any(phrase in data['response'].lower() for phrase in problematic_phrases):
                print("❌ PROBLEMATIC RESPONSE DETECTED!")
            else:
                print("✅ Response looks good!")
            
            print("-" * 50)
            return data
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    print("🧪 Testing improved AI response generation")
    print("=" * 60)
    
    # Test messages that previously caused problematic AI responses
    test_messages = [
        "help me with my workout",           # Previously gave inappropriate response
        "can you give examples?",            # Generic question
        "excuse me?",                       # Confusion response  
        "what should I do about my diet?",  # Should not match quick patterns
        "tell me more about that",          # Follow-up question
        "I don't understand",               # Confusion
    ]
    
    for message in test_messages:
        test_api_chat(message)
    
    print("\n✨ AI improvement testing complete!")