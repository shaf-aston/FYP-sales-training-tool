from chatbot.prompts import _SHARED_RULES
from chatbot.flow import FLOWS
from chatbot.utils import Strategy, Stage
from chatbot.overrides import check_override_condition


def test_shared_rules_exist_and_nonempty():
    assert isinstance(_SHARED_RULES, str)
    # Ensure the shared rules contain at least one of the expected markers
    assert "P1 HARD RULES" in _SHARED_RULES or "ANTI-PARROTING" in _SHARED_RULES


def test_flows_include_consultative_and_transactional():
    # FLOWS keys use the Strategy enum values
    assert Strategy.CONSULTATIVE in FLOWS
    assert Strategy.TRANSACTIONAL in FLOWS
    consult_stages = FLOWS[Strategy.CONSULTATIVE]["stages"]
    # Ensure intent stage is present in consultative flow
    assert Stage.INTENT in consult_stages


def test_override_triggers_for_repetitive_validation():
    # Construct history with repeated assistant validation phrases to trigger the override
    # Note: is_repetitive_validation requires at least 4 history entries to consider a loop
    history = [
        {"role": "user", "content": "Context start"},
        {"role": "assistant", "content": "That makes sense."},
        {"role": "user", "content": "Thanks"},
        {"role": "assistant", "content": "I see."},
    ]

    base_prompt = "BASE"
    user_message = "ok"
    stage = "logical"

    override = check_override_condition(base_prompt, user_message, stage, history, preferences=None)
    assert override is not None
    assert "CONSTRAINT VIOLATION" in override or "Excessive validation" in override
