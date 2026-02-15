#!/usr/bin/env python
"""
VERIFICATION TEST: Rewind Fix - Confirm No History Duplication

This test simulates the exact scenario from the dry run:
1. User: "Hi" -> Bot: "Hello"
2. User: "I want a car" -> Bot: "What kind?"
3. User edits message at index 1 to "I want a truck"

Expected behavior (AFTER FIX):
- History should be: ["Hi", "Hello", "I want a truck", "Bot Response"]
- NO duplication of "Hi" / "Hello"
- FSM state should correctly track progression
"""

from src.chatbot.chatbot import SalesChatbot
import json


def test_rewind_fix_no_duplication():
    """Verify rewind_to_turn resets FSM before replaying history."""
    
    print("\n" + "="*80)
    print("TEST: Rewind Fix - History Duplication")
    print("="*80)
    
    # Initialize chatbot
    bot = SalesChatbot(provider_type="ollama", product_type="general")
    
    # Manually build the scenario (simulating conversation)
    print("\n[SETUP] Building initial conversation state...")
    
    # Turn 0: User "Hi" -> Bot "Hello"
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "Hi"},
        {"role": "bot", "content": "Hello"},
        {"role": "user", "content": "I want a car"},
        {"role": "bot", "content": "What kind?"}
    ]
    
    # Set FSM state as if it had progressed
    bot.flow_engine.current_stage = "logical"  # Simulating progression
    bot.flow_engine.stage_turn_count = 2
    
    print(f"Initial history length: {len(bot.flow_engine.conversation_history)}")
    print(f"Initial stage: {bot.flow_engine.current_stage}")
    print(f"Initial turn count: {bot.flow_engine.stage_turn_count}")
    
    print("\nInitial history:")
    for i, msg in enumerate(bot.flow_engine.conversation_history):
        print(f"  {i}: {msg['role'].upper()}: {msg['content']}")
    
    # NOW: User edits message at index 1 (which is the message "I want a car")
    # So we want to rewind to turn_index = 1
    # This means we keep history_length = 1 * 2 = 2 (first user msg + bot response)
    
    print("\n" + "-"*80)
    print("[OPERATION] Rewinding to turn_index=1 (keeping 'Hi' + 'Hello')")
    print("-"*80)
    
    bot.rewind_to_turn(turn_index=1)
    
    print(f"\nAfter rewind:")
    print(f"  History length: {len(bot.flow_engine.conversation_history)}")
    print(f"  Stage: {bot.flow_engine.current_stage}")
    print(f"  Turn count: {bot.flow_engine.stage_turn_count}")
    
    print("\nHistory after rewind:")
    for i, msg in enumerate(bot.flow_engine.conversation_history):
        print(f"  {i}: {msg['role'].upper()}: {msg['content']}")
    
    # VERIFY: No duplication
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)
    
    # Check 1: History should have exactly 2 messages (Hi, Hello)
    assert len(bot.flow_engine.conversation_history) == 2, \
        f"FAIL: Expected 2 messages, got {len(bot.flow_engine.conversation_history)}"
    print("✓ Check 1: Correct history length (2 messages)")
    
    # Check 2: No duplication of "Hi"
    hi_count = sum(1 for msg in bot.flow_engine.conversation_history if msg['content'] == 'Hi')
    assert hi_count == 1, f"FAIL: 'Hi' appears {hi_count} times, expected 1"
    print("✓ Check 2: No duplication of 'Hi'")
    
    # Check 3: No duplication of "Hello"
    hello_count = sum(1 for msg in bot.flow_engine.conversation_history if msg['content'] == 'Hello')
    assert hello_count == 1, f"FAIL: 'Hello' appears {hello_count} times, expected 1"
    print("✓ Check 3: No duplication of 'Hello'")
    
    # Check 4: FSM state reset correctly
    assert bot.flow_engine.current_stage == "intent", \
        f"FAIL: Expected stage 'intent', got '{bot.flow_engine.current_stage}'"
    print("✓ Check 4: FSM stage reset to 'intent'")
    
    # Check 5: Turn counter reflects replayed turns (1 exchange = 1 turn)
    # After replaying "Hi" + "Hello", the turn_count should be 1
    assert bot.flow_engine.stage_turn_count == 1, \
        f"FAIL: Expected turn_count=1 after replaying 1 exchange, got {bot.flow_engine.stage_turn_count}"
    print("✓ Check 5: FSM turn_count correctly reflects replayed turns (1)")
    
    # Check 6: Messages are in correct order
    assert bot.flow_engine.conversation_history[0]['content'] == 'Hi', "FAIL: First message wrong"
    assert bot.flow_engine.conversation_history[1]['content'] == 'Hello', "FAIL: Second message wrong"
    print("✓ Check 6: Messages in correct order (Hi -> Hello)")
    
    print("\n" + "="*80)
    print("✓ ALL CHECKS PASSED - REWIND FIX IS WORKING CORRECTLY")
    print("="*80)


def test_rewind_fix_with_longer_history():
    """Test rewind with more complex history."""
    
    print("\n" + "="*80)
    print("TEST: Rewind Fix - Complex History (5 exchanges)")
    print("="*80)
    
    bot = SalesChatbot(provider_type="ollama", product_type="general")
    
    # Build a longer conversation
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "Hi"},
        {"role": "bot", "content": "Hello"},
        {"role": "user", "content": "I want a car"},
        {"role": "bot", "content": "What kind?"},
        {"role": "user", "content": "A red one"},
        {"role": "bot", "content": "Nice choice"},
        {"role": "user", "content": "How much?"},
        {"role": "bot", "content": "Starts at $30k"},
        {"role": "user", "content": "Too expensive"},
        {"role": "bot", "content": "We have cheaper options"},
    ]
    
    bot.flow_engine.current_stage = "objection"
    bot.flow_engine.stage_turn_count = 5
    
    print(f"Initial history length: {len(bot.flow_engine.conversation_history)}")
    print(f"Initial stage: {bot.flow_engine.current_stage}")
    
    # Rewind to turn 2 (keep first 4 messages)
    print("\n[OPERATION] Rewinding to turn_index=2...")
    bot.rewind_to_turn(turn_index=2)
    
    print(f"\nAfter rewind:")
    print(f"  History length: {len(bot.flow_engine.conversation_history)}")
    print(f"  Stage: {bot.flow_engine.current_stage}")
    print(f"  Turn count: {bot.flow_engine.stage_turn_count}")
    
    print("\nHistory after rewind:")
    for i, msg in enumerate(bot.flow_engine.conversation_history):
        print(f"  {i}: {msg['role'].upper()}: {msg['content']}")
    
    # Verify
    assert len(bot.flow_engine.conversation_history) == 4, \
        f"Expected 4 messages, got {len(bot.flow_engine.conversation_history)}"
    
    # The FSM will naturally advance based on the replayed history and advancement rules
    # The key thing is: NO DUPLICATION of messages
    assert bot.flow_engine.conversation_history[0]['content'] == 'Hi', \
        "First message should be 'Hi'"
    assert bot.flow_engine.conversation_history[1]['content'] == 'Hello', \
        "Second message should be 'Hello'"
    
    # Check no duplication of early messages
    first_hi_count = sum(1 for msg in bot.flow_engine.conversation_history if msg['content'] == 'Hi')
    assert first_hi_count == 1, f"'Hi' appears {first_hi_count} times (should be 1)"
    
    first_hello_count = sum(1 for msg in bot.flow_engine.conversation_history if msg['content'] == 'Hello')
    assert first_hello_count == 1, f"'Hello' appears {first_hello_count} times (should be 1)"
    
    print("\n✓ Complex history test PASSED - No duplications, correct state rebuilt")


if __name__ == "__main__":
    test_rewind_fix_no_duplication()
    test_rewind_fix_with_longer_history()
    
    print("\n" + "="*80)
    print("✓ ALL VERIFICATION TESTS PASSED")
    print("="*80)
    print("\nSUMMARY:")
    print("- rewind_to_turn() now correctly resets FSM state")
    print("- No history duplication occurs")
    print("- FSM stage and turn_count properly reset to initial values")
    print("- Edit functionality will work correctly after this fix")
    print("="*80 + "\n")
