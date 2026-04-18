"""Probe-based validation: system prompt assembly per stage"""

import json
from src.chatbot.chatbot import SalesChatbot


def test_intent_stage_prompt_contains_elicitation_guidance():
    """INTENT stage prompt should guide toward gathering intent"""
    bot = SalesChatbot(
        provider_type="probe", product_type="cars", session_id="probe_intent"
    )

    # Get response via ProbeProvider (returns full messages as JSON)
    resp = bot.chat("Hi, I'm looking at cars")
    dump = json.loads(resp.content)
    system_prompt = dump["system_prompt"]

    # INTENT stage should emphasize gathering needs, not selling
    assert "intent" in system_prompt.lower() or "understand" in system_prompt.lower(), (
        "INTENT prompt should guide toward understanding user needs"
    )


def test_logical_stage_prompt_differs_from_intent():
    """LOGICAL and INTENT stages should assemble different prompts"""
    # INTENT stage
    bot1 = SalesChatbot(
        provider_type="probe", product_type="cars", session_id="probe_intent"
    )
    resp1 = bot1.chat("I need a reliable sedan")
    intent_prompt = json.loads(resp1.content)["system_prompt"]

    # Advance to LOGICAL (clear intent triggers transition)
    resp2 = bot1.chat("I drive 50 miles daily and need good reliability")
    logical_prompt = json.loads(resp2.content)["system_prompt"]

    # Prompts should differ (different stage = different guidance)
    assert intent_prompt != logical_prompt, (
        "INTENT and LOGICAL stages should have different system prompts"
    )


def test_objection_stage_prompt_contains_sop():
    """OBJECTION stage should include Standard Operating Procedure guidance"""
    bot = SalesChatbot(
        provider_type="probe", product_type="cars", session_id="probe_objection"
    )

    # Drive to objection stage by simulating clear path through intent → logical → emotional → pitch
    turns = [
        "I need a reliable sedan",
        "Daily commute, 50 miles",
        "Budget is around $25k",
        "I'm concerned about reliability and fuel costs",
        "Sounds good, but I'm worried about maintenance costs",
    ]

    for user_input in turns:
        resp = bot.chat(user_input)

    dump = json.loads(resp.content)
    system_prompt = dump["system_prompt"]

    # At objection stage, prompt should reference handling objections
    assert any(
        word in system_prompt.lower()
        for word in ["acknowledge", "reframe", "objection", "address"]
    ), "OBJECTION stage prompt should include SOP guidance (acknowledge, reframe, etc.)"


def test_transactional_vs_consultative_prompts_differ():
    """Transactional and consultative strategies should produce different prompts"""
    # Consultative (cars)
    bot_cons = SalesChatbot(
        provider_type="probe", product_type="cars", session_id="probe_cons"
    )
    resp_cons = bot_cons.chat("Hi")
    cons_prompt = json.loads(resp_cons.content)["system_prompt"]

    # Transactional (fitness_class)
    bot_trans = SalesChatbot(
        provider_type="probe", product_type="fitness_class", session_id="probe_trans"
    )
    resp_trans = bot_trans.chat("Hi")
    trans_prompt = json.loads(resp_trans.content)["system_prompt"]

    # Strategies should produce different guidance
    assert cons_prompt != trans_prompt, (
        "Consultative and transactional strategies should have different prompts"
    )
