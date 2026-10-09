"""AI-buyer replies may not close the deal on their own."""
from core.buyer_guardrails import check_buyer_reply


def test_buyer_reply_cannot_close_the_deal_itself():
    """Only the session rules decide a sale; the AI buyer saying yes is stripped."""
    result = check_buyer_reply(
        "That helps a lot. Let's do it, send the agreement over today. I still want the onboarding details.",
        turn=5,
    )

    assert "buyer_committed" in result.applied_rules
    assert "let's do it" not in result.content.lower()
    assert "onboarding details" in result.content


def test_buyer_reply_normal_answer_passes_untouched():
    reply = "We use spreadsheets right now. Leads slip through when someone is off sick."
    result = check_buyer_reply(reply, turn=1)

    assert result.content == reply
    assert result.applied_rules == []
