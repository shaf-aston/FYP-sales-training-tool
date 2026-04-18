"""Guards the shared user_turn_count property against silent drift."""

from chatbot.flow import SalesFlowEngine


def test_user_turn_count_starts_at_zero():
    engine = SalesFlowEngine(flow_type="consultative", product_context="ctx")
    assert engine.user_turn_count == 0


def test_user_turn_count_increments_per_add_turn():
    engine = SalesFlowEngine(flow_type="consultative", product_context="ctx")
    for i in range(4):
        engine.add_turn(f"user {i}", f"bot {i}")
    assert engine.user_turn_count == 4


def test_user_turn_count_ignores_assistant_only_entries():
    engine = SalesFlowEngine(flow_type="consultative", product_context="ctx")
    engine.conversation_history.append(
        {"role": "assistant", "content": "pre-seeded greeting"}
    )
    assert engine.user_turn_count == 0
    engine.add_turn("hi", "hello")
    assert engine.user_turn_count == 1
