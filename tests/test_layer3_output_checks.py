"""Tests for output guardrails and content filtering."""
from core.response_guardrails import apply_layer3_output_checks
from core.utils import Stage


def test_layer3_blocks_pricing_in_logical_stage_without_direct_request():
    result = apply_layer3_output_checks(
        reply_text="The price is $499 per month. Does that work for you?",
        stage=Stage.LOGICAL,
        user_message="We are still reviewing options.",
    )

    assert result.was_blocked is True
    assert result.was_corrected is False
    assert "blocked_pricing_in_discovery" in result.applied_rules
    assert "price" not in result.content.lower()


def test_layer3_allows_pricing_when_user_asks_for_it():
    result = apply_layer3_output_checks(
        reply_text="The price is $499 per month?",
        stage=Stage.LOGICAL,
        user_message="How much is it and what is the pricing?",
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert result.content == "The price is $499 per month?"
    assert result.applied_rules == []


def test_layer3_keeps_question_marks_unchanged():
    result = apply_layer3_output_checks(
        reply_text="What matters most to you? What have you tried? Can you share more?",
        stage=Stage.INTENT,
        user_message="I am not sure.",
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert result.content == "What matters most to you? What have you tried? Can you share more?"
    assert result.applied_rules == []


def test_layer3_returns_stage_fallback_for_empty_output():
    result = apply_layer3_output_checks(
        reply_text="   ",
        stage=Stage.EMOTIONAL,
        user_message="This is frustrating.",
    )

    assert result.was_blocked is True
    assert result.content
    assert "empty_output_fallback" in result.applied_rules
