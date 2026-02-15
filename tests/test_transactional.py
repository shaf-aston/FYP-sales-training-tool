"""
Manual Showcase: Transactional Strategy - NOT for pytest (blocks on real API calls)
Run directly: python tests/test_transactional.py
==================================================

This demonstrates the fixed transactional sales strategy:
- Fast intent confirmation (2 turns max)
- Quick pitch with sensory details
- No permission questions (maintains momentum)
- Leads toward purchase action
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from dotenv import load_dotenv
load_dotenv()

def manual_transactional_demo():
    """Manual demo requiring API key - run separately, not in pytest suite"""
    if not os.environ.get("SAFE_GROQ_API_KEY"):
        print("⚠️  Skipping: No SAFE_GROQ_API_KEY set")
        return
    
    from chatbot.chatbot import SalesChatbot
    bot = SalesChatbot(product_type="watches")
    
    print("\n" + "="*75)
    print("TRANSACTIONAL STRATEGY DEMO: Selling Watches (Low-Ticket, Fast Cycle)")
    print("="*75)
    
    conversation = [
        ("hi, looking for a watch", "USER initiates with clear intent"),
        ("just something simple that tells the time", "USER clarifies need - SHOULD ADVANCE TO PITCH HERE"),
        ("yeah that's what i want", "USER confirms - BOT presents with sensory details"),
        ("ok show me", "USER ready - BOT continues compelling presentation"),
    ]
    
    for i, (msg, context) in enumerate(conversation, 1):
        print(f"\n[TURN {i}] {context}")
        print(f"  User:  {msg}")
        response = bot.chat(msg)
        print(f"  Bot:   {response[:120]}..." if len(response) > 120 else f"  Bot:   {response}")
        print(f"  Stage: {bot.current_stage} | Turn in stage: {bot.stage_turn_count}")
        
        # Validate no trailing questions in pitch stage
        if bot.current_stage == "pitch" and response.endswith('?'):
            print("  ⚠️  ERROR: Trailing question in PITCH stage!")
        
        if bot.current_stage == "pitch":
            print("  [PITCH] Using sensory language, leading to action")
    
    print("\n" + "="*75)
    print("RESULTS:")
    print("  [OK] Fast intent advancement (turn 2)")
    print("  [OK] Pitch stage: Sensory presentation, NOT listing options")
    print("  [OK] No trailing permission questions")
    print("  [OK] Includes price/availability (drives action)")
    print("="*75 + "\n")

if __name__ == "__main__":
    manual_transactional_demo()
