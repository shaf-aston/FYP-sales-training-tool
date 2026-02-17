"""Temporary status/integration tests - validates current system state

These tests are temporary (for Feb 2026 user study validation)
Will be replaced with comprehensive tests later
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chatbot.chatbot import SalesChatbot
from chatbot.performance import PerformanceTracker
from chatbot.providers import get_available_providers


def test_provider_factory():
    """Verify provider factory returns valid providers"""
    providers = get_available_providers()
    assert isinstance(providers, dict), "Factory returns dict"
    assert 'groq' in providers or 'ollama' in providers, "At least one provider available"
    print("✓ Provider factory working")


def test_performance_tracker():
    """Verify performance tracking logs without crashing"""
    PerformanceTracker.log_stage_latency(
        session_id="test_session_001",
        stage="intent",
        strategy="consultative",
        latency_ms=120.5,
        provider="groq",
        model="llama-3.3-70b",
        user_message_length=15,
        bot_response_length=42
    )
    
    # Verify we can retrieve metrics
    metrics = PerformanceTracker.get_session_metrics("test_session_001")
    assert len(metrics) > 0, "Metrics logged and retrievable"
    assert metrics[0]['stage'] == 'intent', "Stage recorded correctly"
    print("✓ Performance tracking working")


def test_performance_stats():
    """Verify provider stats aggregation"""
    stats = PerformanceTracker.get_provider_stats()
    # Stats may be empty first run, but should be valid dict
    assert isinstance(stats, dict), "Stats returns dict"
    if stats:
        assert 'groq' in stats or 'ollama' in stats, "Provider stats present"
        if 'groq' in stats:
            assert 'avg_latency_ms' in stats['groq'], "Avg latency tracked"
    print("✓ Performance stats aggregation working")


def test_chatbot_with_session_tracking():
    """Verify chatbot stores session_id for metrics"""
    os.environ["GROQ_API_KEY"] = "test_key"
    bot = SalesChatbot(session_id="test_session_002")
    assert bot.session_id == "test_session_002", "Session ID stored"
    # FSM refactor: history in flow_engine
    assert hasattr(bot.flow_engine, 'conversation_history'), "Has conversation history"
    assert bot.flow_engine.current_stage == "intent", "Starts at intent stage"
    print("✓ Chatbot session tracking working")


def test_error_handling():
    """Verify chatbot handles missing provider gracefully"""
    # Create bot with fake provider - should handle gracefully
    os.environ["GROQ_API_KEY"] = "invalid_key"
    bot = SalesChatbot(provider_type="groq", session_id="test_error_001")
    
    # Chat should not crash even with bad provider
    response = bot.chat("Hello")
    assert hasattr(response, 'content'), "Returns ChatResponse object"
    assert len(response.content) > 0, "Returns non-empty response"
    # FSM refactor: history in flow_engine
    assert "trouble" in response.content.lower() or len(bot.flow_engine.conversation_history) > 0, "Handled gracefully"
    print("✓ Error handling working (graceful fallback)")


def test_stage_progression():
    """Verify stage advancement logic"""
    os.environ["GROQ_API_KEY"] = "test_key"
    bot = SalesChatbot()
    
    # FSM refactor: current_stage in flow_engine
    assert bot.flow_engine.current_stage == "intent", "Starts at intent"
    assert bot.flow_engine.flow_type in ["consultative", "transactional"], "Valid flow type"
    
    # Manually advance (simulating successful intent)
    bot.flow_engine.stage_turn_count = 5  # Trigger max turns rule
    bot.flow_engine.advance()
    
    assert bot.flow_engine.current_stage != "intent", "Advances from intent"
    assert bot.flow_engine.flow_type in ["consultative", "transactional"], "Maintains valid flow type"
    print("✓ Stage progression working")


def test_rewind_to_turn():
    """Verify rewind resets to intent stage"""
    os.environ["GROQ_API_KEY"] = "test_key"
    bot = SalesChatbot()
    
    # FSM refactor: simulate conversation history
    bot.flow_engine.conversation_history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"}
    ]
    bot.flow_engine.stage_turn_count = 5
    bot.flow_engine.current_stage = "logical"
    
    # Rewind to turn 0
    bot.rewind_to_turn(0)
    
    # FSM refactor: check flow_engine state
    assert bot.flow_engine.current_stage == "intent", "Rewind resets to intent"
    assert len(bot.flow_engine.conversation_history) == 0, "History truncated"
    print("✓ Rewind/edit working")


if __name__ == "__main__":
    try:
        test_provider_factory()
        test_performance_tracker()
        test_performance_stats()
        test_chatbot_with_session_tracking()
        test_error_handling()
        test_stage_progression()
        test_rewind_to_turn()
        
        print("\n" + "="*50)
        print("✅ ALL STATUS TESTS PASSED (7/7)")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
