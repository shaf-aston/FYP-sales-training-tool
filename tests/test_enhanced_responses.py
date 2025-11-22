"""
Test script for enhanced_responses module
"""



import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.fallback_responses import (
    generate_ai_response,
    post_process_response,
    get_mary_fallback,
    handle_error_response
)

def test_cleanup():
    """Test the response cleanup functionality"""
    print("\n=== Testing Response Cleanup ===")
    
    test_responses = [
        "I'm hoping you can help me figure out the best approach.",
        "INSTRUCTION: Respond as Mary, a 65-year-old woman with arthritis",
        "Coach: What exercises do you like? Mary: I enjoy walking",
        "* I used to walk regularly but haven't done structured exercise in years",
        "",
        "ai assistant model should respond as if it's Mary" 
    ]
    
    for i, response in enumerate(test_responses):
        print(f"\nTest {i+1}: {response[:30]}...")
        cleaned = post_process_response(response, 0)
        print(f"Cleaned: {cleaned}")

def test_character_fallbacks():
    """Test character-specific fallbacks"""
    print("\n=== Testing Character Fallbacks ===")
    
    characters = ["mary_senior", "jake_athlete", "sarah_mom", "tom_executive", "unknown_character"]
    
    for character in characters:
        fallback = get_mary_fallback()
        print(f"{character}: {fallback}")

def test_post_processing():
    """Test post-processing enhancement"""
    print("\n=== Testing Post-Processing ===")
    
    test_cases = [
        ("I'm not sure what to do about my fitness routine.", "mary_senior", 123),
        ("Could you provide some tips for me?", "jake_athlete", 456),
        ("I would appreciate any advice you can give me.", "sarah_mom", 789),
        ("I'm still learning about fitness.", "tom_executive", 101)
    ]
    
    for response, character, msg_hash in test_cases:
        print(f"\nOriginal ({character}): {response}")
        enhanced = post_process_response(response, msg_hash)
        print(f"Enhanced: {enhanced}")
        
def test_error_handling():
    """Test error response handling"""
    print("\n=== Testing Error Handling ===")
    
    characters = ["mary_senior", "jake_athlete", "sarah_mom", "tom_executive"]
    
    for character in characters:
        error_resp = handle_error_response(Exception("Test error"))
        print(f"{character}: {error_resp}")

def mock_pipeline(prompt, **kwargs):
    """Mock pipeline for testing generate_ai_response"""
    return [{"generated_text": prompt + "\nI'm hoping you can help me figure out the best approach for my fitness goals."}]

def test_generate_response():
    """Test generate_ai_response with a mock pipeline"""
    print("\n=== Testing Generate Response ===")
    
    class MockPipe:
        def __call__(self, prompt, **kwargs):
            return [{"generated_text": prompt + "\nI'm hoping you can help me figure out the best approach for my fitness goals."}]
    
    mock_pipe = MockPipe()
    mock_pipe.tokenizer = type('MockTokenizer', (), {})()
    mock_pipe.tokenizer.eos_token_id = 0
    
    prompt = "Coach: What are your fitness goals?"
    response = generate_ai_response(prompt, mock_pipe)
    print(f"Prompt: {prompt}")
    print(f"Generated: {response}")

if __name__ == "__main__":
    print("Testing enhanced_responses module")
    test_cleanup()
    test_character_fallbacks()
    test_post_processing()
    test_error_handling()
    test_generate_response()
    print("\nAll tests completed")