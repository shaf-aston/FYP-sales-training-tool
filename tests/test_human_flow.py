"""Manual conversation flow testing - NOT for pytest (blocks on real API calls)
Run directly: python tests/test_human_flow.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

def manual_conversation_test():
    """Manual test requiring API key - run separately, not in pytest suite"""
    if not os.environ.get("SAFE_GROQ_API_KEY"):
        print("⚠️  Skipping: No SAFE_GROQ_API_KEY set")
        return
    
    from chatbot.chatbot import SalesChatbot
    bot = SalesChatbot(product_type="general")

    print("="*60)
    print("TESTING: Casual conversation flow")
    print("Expected: Human responses, not always questions")
    print("="*60)

    messages = [
        "hi",
        "how are you",
        "nice, whats good with you",
        "are you happy with everything?",
    ]

    for msg in messages:
        print(f"\n👤 USER: {msg}")
        response = bot.chat(msg)
        print(f"🤖 BOT: {response.content}")
        print(f"   ⏱️  Latency: {response.latency_ms:.1f}ms")
        
        # Check if always ending with question
        if response.content.endswith('?'):
            print("   ⚠️  [Ends with question]")
        else:
            print("   ✓ [Statement/mixed response]")

    print("\n" + "="*60)
    print("VALIDATION:")
    print("✓ Should have mix of statements and questions")
    print("✓ Should acknowledge user's questions before redirecting")
    print("✓ Should feel conversational, not interrogative")
    print("="*60)

if __name__ == "__main__":
    manual_conversation_test()
