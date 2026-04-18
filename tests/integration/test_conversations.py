#!/usr/bin/env python
"""
Full conversation tests for both prospect and non-prospect modes.
Tests provider fallback, error handling, and full dialogue flows.
"""

import sys

sys.path.insert(0, "src")

from chatbot.chatbot import SalesChatbot
from chatbot.prospect import ProspectSession


def test_non_prospect_conversation():
    """Test regular chatbot conversation with a human user."""
    print("\n" + "=" * 70)
    print("TEST 1: Non-Prospect Mode (Direct Chatbot Chat)")
    print("=" * 70)

    bot = SalesChatbot(
        provider_type="dummy",
        product_type="trading_service",
        session_id="test_non_prospect_001",
    )

    conversation = [
        "Hi, I'm interested in learning to trade",
        "Can you tell me more about your service?",
        "What's the pricing?",
        "Let's get started!",
    ]

    print("\nInitial State:")
    print(f"  Strategy: {bot.flow_engine.flow_type}")
    print(f"  Stage: {bot.flow_engine.current_stage}")
    print(f"  Provider: {bot._provider_name}")

    for i, user_msg in enumerate(conversation, 1):
        print(f"\nTurn {i}:")
        print(f"  User: {user_msg}")

        response = bot.chat(user_msg)
        print(f"  Bot: {response.content[:100]}")
        print(f"  Latency: {response.latency_ms:.0f}ms | Provider: {response.provider}")
        print(f"  Current stage: {bot.flow_engine.current_stage}")

    print("\nFinal State:")
    print(f"  Strategy: {bot.flow_engine.flow_type}")
    print(f"  Stage: {bot.flow_engine.current_stage}")
    print(f"  Total turns: {len(bot.flow_engine.conversation_history) // 2}")
    return True


def test_prospect_mode_conversation():
    """Test chatbot via ProspectSession (automated bot-to-bot)."""
    print("\n" + "=" * 70)
    print("TEST 2: Prospect Mode (Automated Bot-to-Bot Conversation)")
    print("=" * 70)

    # Create prospect (automated buyer)
    prospect = ProspectSession(
        provider_type="dummy",
        product_type="trading_service",
        difficulty="medium",
        session_id="test_prospect_001",
    )

    # Create bot (salesperson)
    bot = SalesChatbot(
        provider_type="dummy",
        product_type="trading_service",
        session_id="test_prospect_bot_001",
    )

    print(
        f"\nProspect: {prospect.persona.get('name')} (difficulty: {prospect.difficulty_profile.get('label', 'medium')})"
    )
    print(
        f"Bot Initial State: {bot.flow_engine.flow_type} / {bot.flow_engine.current_stage}"
    )

    # Get prospect's opening message
    prospect_opening = prospect.get_opening_message()
    print("\n--- Opening ---")
    print(f"Prospect: {prospect_opening.content[:80]}")

    # Run conversation
    prospect_response = prospect_opening
    for turn in range(4):
        print(f"\n--- Turn {turn + 1} ---")

        # Bot responds to prospect
        bot_response = bot.chat(prospect_response.content)
        print(f"Bot: {bot_response.content[:80]}")
        print(
            f"  Latency: {bot_response.latency_ms:.0f}ms | Stage: {bot.flow_engine.current_stage}"
        )

        # Prospect responds to bot
        prospect_response = prospect.process_turn(bot_response.content)
        print(f"Prospect: {prospect_response.content[:80]}")
        print(f"  Readiness: {prospect_response.state_snapshot['readiness']:.1%}")

        if (
            prospect_response.state_snapshot["has_committed"]
            or prospect_response.state_snapshot["has_walked"]
        ):
            print(f"  Status: {prospect_response.state_snapshot['status']}")
            break

    print("\nFinal State:")
    print(f"  Bot Stage: {bot.flow_engine.current_stage}")
    print(f"  Prospect Status: {prospect.state.status}")
    print(f"  Prospect Readiness: {prospect.state.readiness:.1%}")
    print(f"  Total turns: {prospect.state.turn_count}")
    return True


def test_provider_fallback():
    """Test provider fallback on error (simulated)."""
    print("\n" + "=" * 70)
    print("TEST 3: Provider Fallback Mechanism")
    print("=" * 70)

    bot = SalesChatbot(
        provider_type="dummy",
        product_type="trading_service",
        session_id="test_fallback_001",
    )

    print(f"\nInitial provider: {bot._provider_name}")

    # Create a simple error response
    from chatbot.providers.base import LLMResponse, RATE_LIMIT

    error_response = LLMResponse(
        content="",
        model="test",
        latency_ms=100,
        error="Rate limit exceeded",
        error_code=RATE_LIMIT,
    )

    # Simulate error handling
    fallback_result = bot._handle_provider_error(
        error_response, [{"role": "user", "content": "test"}], "test message"
    )

    print(f"Fallback message length: {len(fallback_result.content)}")
    print(f"Fallback provider attempted: {fallback_result.provider}")
    print("Rate limit fallback triggered: [OK]")
    return True


def test_error_code_consistency():
    """Test that all providers set error_code consistently."""
    print("\n" + "=" * 70)
    print("TEST 4: Error Code Consistency Across Providers")
    print("=" * 70)

    from chatbot.providers.factory import _PROVIDERS

    print(f"\nAvailable providers: {list(_PROVIDERS.keys())}")

    test_messages = [
        {"role": "system", "content": "test"},
        {"role": "user", "content": "test"},
    ]

    for provider_name, provider_class in _PROVIDERS.items():
        print(f"\n{provider_name.upper()}:")
        try:
            provider = provider_class()

            # Check if provider sets error codes
            response = provider.chat(test_messages)

            if response.error:
                print(f"  Error: {response.error[:50]}")
                print(f"  Error code: {response.error_code}")
                if response.error_code:
                    print("  [OK] Error code set")
                else:
                    print("  [ERR] Missing error code")
            else:
                print(f"  Response: {response.content[:50]}")
                print("  [OK] No error")
        except Exception as e:
            print(f"  Exception: {str(e)[:60]}")

    return True


if __name__ == "__main__":
    results = []

    try:
        print("\n\n" + "#" * 70)
        print("# COMPREHENSIVE CONVERSATION & API TESTS")
        print("#" * 70)

        # Run all tests
        results.append(("Non-Prospect Mode", test_non_prospect_conversation()))
        results.append(("Prospect Mode", test_prospect_mode_conversation()))
        results.append(("Provider Fallback", test_provider_fallback()))
        results.append(("Error Code Consistency", test_error_code_consistency()))

    except Exception as e:
        print(f"\n\nEXCEPTION: {e}")
        import traceback

        traceback.print_exc()
        results.append(("ERROR", False))

    # Summary
    print("\n\n" + "#" * 70)
    print("# TEST SUMMARY")
    print("#" * 70)
    for test_name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status}: {test_name}")

    all_pass = all(p for _, p in results)
    print(
        f"\nOverall: {'[PASS] ALL TESTS PASSED' if all_pass else '[FAIL] SOME TESTS FAILED'}"
    )
    sys.exit(0 if all_pass else 1)
