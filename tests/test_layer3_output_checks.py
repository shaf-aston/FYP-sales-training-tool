"""Tests for LAYER 3 response guardrails."""
from core.response_guardrails import apply_layer3_output_checks, check_buyer_reply
from core.utils import Stage, Strategy


def test_layer3_blocks_pricing_in_logical_stage_without_direct_request():
    result = apply_layer3_output_checks(
        reply_text="The price is $499 per month. Does that work for you?",
        stage=Stage.LOGICAL,
        user_message="We are still reviewing options.",
    )

    assert result.was_blocked is True
    assert result.was_corrected is False
    assert "early_price" in result.applied_rules
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


def test_layer3_strips_unasked_pricing_in_transactional_pitch():
    result = apply_layer3_output_checks(
        reply_text="The investment is £499 per month and includes full support and onboarding.",
        stage=Stage.PITCH,
        user_message="Sounds good, tell me about onboarding.",
        flow_type=Strategy.TRANSACTIONAL,
    )

    assert result.was_blocked is True or result.was_corrected is True
    assert "499" not in result.content


def test_layer3_answers_price_when_asked_in_transactional_pitch():
    """The buyer asked; dodging the price is the bug, not the fix."""
    reply = "It's £499 per month, which includes full support and onboarding for your team."
    result = apply_layer3_output_checks(
        reply_text=reply,
        stage=Stage.PITCH,
        user_message="ok fine, what does it cost?",
        flow_type=Strategy.TRANSACTIONAL,
        product_context="Plans: £499 per month.",
    )

    assert result.content == reply
    assert result.applied_rules == []


def test_layer3_strips_invented_price_at_any_stage():
    result = apply_layer3_output_checks(
        reply_text=(
            "Great, signing up takes two minutes on our website. "
            "The Essential Plan is $99/month and Professional is $199/month."
        ),
        stage=Stage.OUTCOME,
        user_message="let's do it, how do I sign up?",
        product_context="Foundation Plan: $199/month.",
    )

    assert "invented_price" in result.applied_rules
    assert "99" not in result.content.replace("199", "")
    assert "signing up takes two minutes" in result.content


def test_layer3_price_question_fallback_never_restarts_discovery():
    """Nothing left after stripping + buyer asked price -> a price-aware line, not 'what brought you in'."""
    result = apply_layer3_output_checks(
        reply_text="It's $99 per month for everything.",
        stage=Stage.INTENT,
        user_message="What does it cost?",
        product_context="No prices listed.",
    )

    assert result.was_blocked is True
    assert "brought you in" not in result.content
    assert "depends" in result.content.lower()


def test_layer3_allows_budget_question_in_discovery():
    reply = "That makes sense. What budget range were you planning for this, roughly?"
    result = apply_layer3_output_checks(
        reply_text=reply,
        stage=Stage.INTENT,
        user_message="Honestly that seems too expensive for us",
    )

    assert result.content == reply


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


def test_layer3_truncates_oversized_response():
    long_text = "This is a valid sentence with no pricing content. " * 40
    result = apply_layer3_output_checks(
        reply_text=long_text,
        stage=Stage.LOGICAL,
        user_message="Tell me more.",
    )

    assert result.was_corrected is True
    assert result.was_blocked is False
    assert len(result.content) <= 1500
    assert "oversized_output_truncated" in result.applied_rules


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
    assert "early_price" in result.applied_rules
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


def test_buyer_reply_cannot_close_the_deal_itself():
    """Only the session rules decide a sale; the AI buyer saying yes is stripped."""
    result = check_buyer_reply(
        "That helps a lot. Let's do it, send the agreement over today. I still want the onboarding details.",
        turn=5,
    )

    assert "buyer_committed" in result.applied_rules
    assert "let's do it" not in result.content.lower()
    assert "onboarding details" in result.content


def test_buyer_reply_out_of_character_falls_back():
    result = check_buyer_reply("As an AI language model, I can't buy software.", turn=2)

    assert result.was_blocked is True
    assert "ai" not in result.content.lower().split()


def test_buyer_reply_normal_answer_passes_untouched():
    reply = "We use spreadsheets right now. Leads slip through when someone is off sick."
    result = check_buyer_reply(reply, turn=1)

    assert result.content == reply
    assert result.applied_rules == []
