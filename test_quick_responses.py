#!/usr/bin/env python3
"""
Quick test script for the improved quick response patterns
This tests the pattern matching without loading the AI model
"""
import re

# Copy of the updated function for testing
def get_character_profile(character_type: str = "mary_senior"):
    """Mock character profile for testing"""
    CHARACTER_PROFILES = {
        "mary_senior": {
            "name": "Mary",
            "age": 65,
            "weight": 175,
            "height": "5'6\"",
            "status": "recently retired",
            "goals": ["lose weight", "gain strength safely"]
        }
    }
    return CHARACTER_PROFILES.get(character_type, CHARACTER_PROFILES["mary_senior"])

def get_character_quick_patterns(character_type: str) -> dict:
    """Get character-specific quick response patterns with improved matching"""
    character = get_character_profile(character_type)
    
    base_patterns = {
        # More specific greeting patterns
        "^(hello|hi|hey)$|^(hello|hi|hey) there": f"Hi there! I'm {character['name']}. It's so nice to meet you!",
        "how are you|how do you feel": f"I'm doing well, thank you for asking! A bit nervous but excited to get started.",
        "how can i help you|can i help|help you": f"Oh, that's so kind of you to ask! I'm actually here looking for help with my fitness goals. I'm hoping you can guide me.",
        "how old are you|what's your age|your age": f"I'm {character['age']} years old. I know I'm not getting any younger, but I'm determined to get healthier!",
        "what are your goals|your goals|what do you want to achieve": f"Well, I really want to {' and '.join(character['goals'])}, but I want to do it safely.",
        # Food and nutrition patterns
        "what do you like to eat|what do you eat|your diet|eating habits": f"I try to eat healthy, but I'll be honest - I could use some guidance on nutrition too. What would you recommend for someone like me?",
        "do you cook|cooking|meal prep": f"I do cook for myself, though I'm not always sure if I'm making the healthiest choices. Do you have any simple, healthy meal ideas?"
    }
    
    # Character-specific patterns with better precision
    if character_type == "mary_senior":
        base_patterns.update({
            "(knee|knees).*(arthritis|pain|hurt|up|about)|arthritis.*(knee|knees)|knee.*problem|\\bknees\\?": "Oh yes, my knees! They've been giving me trouble lately with the arthritis. I'm really worried about making it worse.",
            "(back|lower back).*(pain|hurt|ache)|back pain": "My lower back does bother me sometimes, especially when I've been sitting too long. It's one of my concerns.",
            "\\b(retired|retirement)\\b|\\bteaching\\b.*\\b(job|work|career)": "I just retired recently from teaching! It's exciting to finally have time for myself, but also a bit overwhelming.",
            "(what.*weight|how much.*weigh|your weight)": "I'm about 175 pounds right now, which is more than I'd like to be. I'd really like to get that down.",
            "(exercise|workout|training).*(history|experience|background)": "I used to walk regularly, but I haven't done any real structured exercise in years. I'm not even sure where to start!"
        })
    
    return base_patterns

def test_quick_response(message: str, character_type: str = "mary_senior") -> str:
    """Test function to check quick response patterns"""
    quick_patterns = get_character_quick_patterns(character_type)
    message_lower = message.lower().strip()
    
    print(f"\nTesting message: '{message}'")
    print(f"Character: {character_type}")
    
    for pattern, quick_response in quick_patterns.items():
        if re.search(pattern, message_lower, re.IGNORECASE):
            print(f"✅ MATCHED pattern: {pattern}")
            print(f"📝 Response: {quick_response}")
            return quick_response
    
    print("❌ No quick pattern matched - would use AI generation")
    return None

# Test cases
if __name__ == "__main__":
    print("🧪 Testing improved quick response patterns")
    print("=" * 50)
    
    # Test cases that were problematic before
    test_cases = [
        "hey, what do you like to eat?",  # Should NOT match greeting
        "hi there",                        # Should match greeting
        "hello",                           # Should match greeting
        "how are you doing?",             # Should match "how are you"
        "what do you eat for breakfast?",  # Should match food pattern
        "tell me about your weight",      # Should match weight pattern
        "hey what's up with your knees?", # Should match knee pattern
        "what about your knees?",         # Should match knee pattern
        "what kind of exercise do you do?", # Should NOT match exercise history pattern
        "what's your exercise history?",   # Should match exercise history pattern
        "help me with my workout",         # Should NOT match any pattern
        "how can i help you?",            # Should match "help you" pattern
        "are you retired?",               # Should match retirement pattern
        "do you have back pain?",         # Should match back pain pattern
    ]
    
    for test_message in test_cases:
        test_quick_response(test_message)
        print("-" * 40)
    
    print("\n✨ Testing complete!")