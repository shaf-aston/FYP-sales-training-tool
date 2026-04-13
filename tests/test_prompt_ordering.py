"""Tests to verify prompt assembly ordering and provider payloads."""

from types import SimpleNamespace

from chatbot.chatbot import SalesChatbot
from chatbot.content import generate_stage_prompt


def test_generate_stage_prompt_component_order():
    history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    pre_state = SimpleNamespace(decisive=False, intent="low", guarded=False, question_fatigue=False)

    prompt = generate_stage_prompt(
        strategy="consultative",
        stage="intent",
        product_context="Test Product",
        history=history,
        user_message="I need a car",
        pre_state=pre_state,
    )

    # Basic component presence
    assert "PRODUCT: Test Product" in prompt
    assert "=== TURN CONTEXT ===" in prompt
    assert "RECENT CONVERSATION:" in prompt

    # Ordering assertions: base -> turn context -> stage -> recent conversation
    prod_idx = prompt.find("PRODUCT:")
    turn_idx = prompt.find("=== TURN CONTEXT ===")
    stage_idx = prompt.find("STAGE: INTENT")
    recent_idx = prompt.find("RECENT CONVERSATION:")

    assert prod_idx != -1 and turn_idx != -1 and stage_idx != -1 and recent_idx != -1
    assert prod_idx < turn_idx < stage_idx < recent_idx

    # Tactic/adaptation guidance (low-intent consultative) should appear after recent conversation
    assert ("TACTIC OVERRIDE" in prompt) or ("ADAPTATION" in prompt)
    tactic_idx = prompt.find("TACTIC OVERRIDE") if "TACTIC OVERRIDE" in prompt else prompt.find("ADAPTATION")
    assert recent_idx < tactic_idx


def test_chat_builds_messages_and_duplicates_history():
    bot = SalesChatbot(provider_type="dummy", model=None, product_type=None, session_id="ordering_test")

    # populate history with two turns
    bot.flow_engine.add_turn("Hello", "Hi there")
    bot.flow_engine.add_turn("I need help", "Tell me more")

    captured = {}
    original_chat = bot.provider.chat

    def probe_chat(messages, temperature=0.8, max_tokens=200, stage=None):
        # capture the messages passed to the provider then delegate to original
        captured["messages"] = messages
        return original_chat(messages, temperature=temperature, max_tokens=max_tokens, stage=stage)

    # monkeypatch provider.chat for inspection
    bot.provider.chat = probe_chat

    bot.chat("Final question")

    assert "messages" in captured
    msgs = captured["messages"]

    # First message should be the assembled system prompt
    assert msgs[0]["role"] == "system"
    assert "RECENT CONVERSATION:" in msgs[0]["content"]

    # Recent conversation should also appear as separate message objects (duplication)
    assert any(m for m in msgs[1:-1] if m.get("role") == "user" and "Hello" in m.get("content", ""))

    # Last message should be the user's current turn
    assert msgs[-1]["role"] == "user" and msgs[-1]["content"] == "Final question"


def test_override_short_circuit():
    # A direct info request should trigger the override template and short-circuit
    s = generate_stage_prompt(
        strategy="consultative",
        stage="intent",
        product_context="Test Product",
        history=[],
        user_message="what options",
    )

    assert "IMMEDIATE ACTION REQUIRED" in s
