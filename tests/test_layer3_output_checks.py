"""Tests for LAYER 3 response guardrails."""
from core.response_guardrails import apply_layer3_output_checks
from core.utils import Stage, Strategy


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
        reply_text="The price is $499 per month. That covers everything you mentioned.",
        stage=Stage.LOGICAL,
        user_message="How much is it and what is the pricing?",
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert result.applied_rules == []


def test_layer3_blocks_pricing_in_transactional_pitch():
    result = apply_layer3_output_checks(
        reply_text="The investment is £499 per month and includes full support and onboarding.",
        stage=Stage.PITCH,
        user_message="What does it cost?",
        flow_type=Strategy.TRANSACTIONAL,
    )

    assert result.was_blocked is True or result.was_corrected is True
    assert "price" not in result.content.lower()


def test_layer3_passes_through_negotiation_stage():
    result = apply_layer3_output_checks(
        reply_text="The total is £499 per month, and we can talk through payment timing now.",
        stage=Stage.NEGOTIATION,
        user_message="Can we look at payment options?",
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert result.applied_rules == []


def test_layer3_keeps_question_marks_unchanged():
    result = apply_layer3_output_checks(
        reply_text="What matters most to you? What have you tried? Can you share more about the situation?",
        stage=Stage.INTENT,
        user_message="I am not sure.",
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert "?" in result.content
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


def test_layer3_blocks_degenerate_short_response():
    result = apply_layer3_output_checks(
        reply_text="Got it.",
        stage=Stage.LOGICAL,
        user_message="Tell me more.",
    )

    assert result.was_blocked is True
    assert "empty_output_fallback" in result.applied_rules


def test_layer3_blocks_oversized_response():
    long_text = "This is a valid sentence with no pricing content. " * 40
    result = apply_layer3_output_checks(
        reply_text=long_text,
        stage=Stage.LOGICAL,
        user_message="Tell me more.",
    )

    assert result.was_blocked is True
    assert "oversized_output_fallback" in result.applied_rules


def test_layer3_corrects_pricing_when_other_content_is_substantial():
    result = apply_layer3_output_checks(
        reply_text=(
            "Tell me about your current workflow and what's not clicking for you. "
            "Our packages start at £200 per month for the entry tier. "
            "What outcome would make the biggest difference to your team right now?"
        ),
        stage=Stage.LOGICAL,
        user_message="We are still reviewing options.",
    )

    assert result.was_corrected is True
    assert result.was_blocked is False
    assert "corrected_pricing_in_discovery" in result.applied_rules
    assert "per month" not in result.content
    assert len(result.content) >= 40


def test_layer3_catches_per_year_pricing():
    result = apply_layer3_output_checks(
        reply_text="The service runs at £2,400 per year and scales with your usage.",
        stage=Stage.INTENT,
        user_message="I want to understand the product.",
    )

    assert result.was_blocked is True or result.was_corrected is True
    assert "per year" not in result.content


def test_layer3_catches_annually_pricing():
    result = apply_layer3_output_checks(
        reply_text="Billed annually, you would save around 20 percent compared to monthly billing.",
        stage=Stage.EMOTIONAL,
        user_message="What are the options?",
    )

    assert result.was_blocked is True or result.was_corrected is True


def test_layer3_passes_through_consultative_pitch():
    result = apply_layer3_output_checks(
        reply_text="The investment is £499 per month and includes full support and onboarding.",
        stage=Stage.PITCH,
        user_message="What does it cost?",
        flow_type=Strategy.CONSULTATIVE,
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert result.applied_rules == []


def test_layer3_preserves_consequence_of_inaction_language_in_emotional_stage():
    result = apply_layer3_output_checks(
        reply_text="What would the cost of staying the same be day to day for your team?",
        stage=Stage.EMOTIONAL,
        user_message="We're not asking about pricing here.",
    )

    assert result.was_blocked is False
    assert result.was_corrected is False
    assert "cost of staying the same" in result.content.lower()
