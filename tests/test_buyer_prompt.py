"""What the AI buyer is told: the product, the learner's custom knowledge, and the persona once."""

import core.knowledge as knowledge_module
import core.loader as loader
from core import buyer_session
from core.buyer_prompt import build_system_prompt


def test_sell_session_prompt_has_product_custom_data_and_persona_once(monkeypatch, stub_buyer):
    monkeypatch.setattr(
        buyer_session,
        "load_buyer_config",
        lambda: {
            "difficulty_profiles": {
                "easy": {
                    "behaviour": {
                        "initial_readiness": 0.5,
                        "readiness_gain_per_good_turn": 0.12,
                        "readiness_loss_per_bad_turn": 0.05,
                        "max_objections": 1,
                        "patience_turns": 15,
                    }
                }
            },
            "default_difficulty": "easy",
            "behaviour_rules": {"easy": "Be friendly."},
        },
    )
    monkeypatch.setattr(
        loader,
        "load_buyer_products",
        lambda: {"products": {"b2b_saas": {"context": "Workflow software", "knowledge": "Core product knowledge."}}},
    )
    monkeypatch.setattr(
        knowledge_module,
        "get_custom_knowledge_text",
        lambda: "product_name: Acme Pro\nAdditional notes: buyer research",
    )

    session = buyer_session.BuyerSession(
        provider_type="stub",
        product_type="b2b_saas",
        difficulty="easy",
        persona={
            "name": "Nina",
            "needs": ["workflow automation"],
            "pain_points": ["manual reporting"],
            "budget": "$20-$40",
            "background": "Ops lead",
            "personality": "Pragmatic",
        },
        session_id="sell123",
    )

    assert "Workflow software" in session.product_context
    assert "Core product knowledge." in session.product_context
    assert loader.load_buyer_config()["research_notes_heading"] in session.product_context
    assert "product_name: Acme Pro" in session.product_context
    assert "Additional notes: buyer research" in session.product_context

    prompt = build_system_prompt(
        loader.load_buyer_config()["system_prompt_template"],
        persona=session.persona,
        readiness=0.5,
        product_context=session.product_context,
        behaviour_rules="",
    )
    for persona_fact in ("workflow automation", "manual reporting", "$20-$40"):
        assert prompt.count(persona_fact) == 1
