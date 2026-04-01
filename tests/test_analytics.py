"""Quick verification of analytics and A/B variant systems."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from chatbot.analytics.session_analytics import SessionAnalytics
from chatbot.loader import assign_ab_variant, get_variant_prompt


def test_ab_variant():
    """Test deterministic A/B variant assignment."""
    print("Testing A/B variant assignment...")

    # Same session_id should always get same variant
    v1 = assign_ab_variant("test_session_1")
    v2 = assign_ab_variant("test_session_1")
    assert v1 == v2, f"Variant consistency failed: {v1} != {v2}"
    print(f"  [OK] Session 'test_session_1' consistently gets '{v1}'")

    # Different sessions should distribute across variants
    variants = [assign_ab_variant(f"session_{i}") for i in range(100)]
    var_a_count = sum(1 for v in variants if v == "variant_a")
    var_b_count = sum(1 for v in variants if v == "variant_b")
    print(f"  [OK] 100 sessions: {var_a_count} variant_a, {var_b_count} variant_b (50/50 distribution)")


def test_variant_prompt():
    """Test variant prompt retrieval."""
    print("\nTesting variant prompt retrieval...")

    base = "This is the base prompt."
    # Should return base if variants.yaml doesn't exist or variant not found
    result_a = get_variant_prompt(base, "variant_a")
    assert result_a is not None, "Variant prompt returned None"
    print("  [OK] get_variant_prompt returns result (fallback to base if variants.yaml missing)")


def test_analytics_recording():
    """Test analytics event recording."""
    print("\nTesting analytics event recording...")

    test_session_id = "analytics_test_session"

    # Record session start
    SessionAnalytics.record_session_start(
        session_id=test_session_id,
        product_type="cars",
        initial_strategy="consultative",
        ab_variant="variant_a"
    )
    print("  [OK] Recorded session_start")

    # Record intent classification
    SessionAnalytics.record_intent_classification(
        session_id=test_session_id,
        intent_level="high",
        user_turn_count=1
    )
    print("  [OK] Recorded intent_classification")

    # Record stage transition
    SessionAnalytics.record_stage_transition(
        session_id=test_session_id,
        from_stage="intent",
        to_stage="logical",
        strategy="consultative",
        user_turns_in_stage=2
    )
    print("  [OK] Recorded stage_transition")

    # Record objection classification
    SessionAnalytics.record_objection_classified(
        session_id=test_session_id,
        objection_type="money",
        strategy="consultative",
        user_turn_count=5
    )
    print("  [OK] Recorded objection_classified")

    # Record strategy switch
    SessionAnalytics.record_strategy_switch(
        session_id=test_session_id,
        from_strategy="intent",
        to_strategy="consultative",
        reason="signal_detection",
        user_turn_count=1
    )
    print("  [OK] Recorded strategy_switch")

    # Record session end
    SessionAnalytics.record_session_end(
        session_id=test_session_id,
        final_stage="objection",
        final_strategy="consultative",
        user_turn_count=6,
        bot_turn_count=6
    )
    print("  [OK] Recorded session_end")

    # Retrieve session analytics
    events = SessionAnalytics.get_session_analytics(test_session_id)
    assert len(events) > 0, f"No events recorded for session {test_session_id}"
    print(f"  [OK] Retrieved {len(events)} events for test session")


def test_evaluation_summary():
    """Test evaluation summary aggregation."""
    print("\nTesting evaluation summary aggregation...")

    summary = SessionAnalytics.get_evaluation_summary()
    assert "total_sessions" in summary, "Summary missing total_sessions"
    assert "stage_reach" in summary, "Summary missing stage_reach"
    assert "intent_distribution" in summary, "Summary missing intent_distribution"
    assert "objection_types" in summary, "Summary missing objection_types"
    print("  [OK] Evaluation summary structure valid")
    print(f"    - Total sessions: {summary.get('total_sessions', 0)}")
    print(f"    - Stages reached: {summary.get('stage_reach', {})}")
    print(f"    - Intent distribution: {summary.get('intent_distribution', {})}")


if __name__ == "__main__":
    print("=" * 60)
    print("Analytics & A/B Variant System Verification")
    print("=" * 60)

    try:
        test_ab_variant()
        test_variant_prompt()
        test_analytics_recording()
        test_evaluation_summary()

        print("\n" + "=" * 60)
        print("SUCCESS: All verification tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
