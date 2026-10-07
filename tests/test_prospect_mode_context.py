# Tests for prospect-mode context assembly and custom knowledge injection.

import core.knowledge as knowledge_module
import core.loader as loader
import core.buyer_session as prospect_session


class _StubProvider:
    def is_available(self):
        return True

    provider_name = "stub"

    def __init__(self):
        self.chat_calls = []

    def chat(self, messages, temperature=0.7, max_tokens=150):
        self.chat_calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        return type("Resp", (), {"content": "hello"})()

    def get_model_name(self):
        return "stub-model"


def test_prospect_session_prompt_has_product_custom_data_and_persona_once(monkeypatch):
    # Product and custom notes form the context; the persona is stated once, by the template.
    monkeypatch.setattr(
        prospect_session,
        "load_prospect_config",
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
            "behaviour_rules": {"easy": "Be friendly."},
            "prospect_mode": {
                "max_turns": 5,
                "scoring_enabled": True,
                "feedback_style": "coaching",
            },
        },
    )
    monkeypatch.setattr(
        "core.services.provider_router.create_provider",
        lambda *_args, **_kwargs: _StubProvider(),
    )
    monkeypatch.setattr(
        loader,
        "load_product_config",
        lambda: {
            "products": {
                "b2b_saas": {
                    "context": "Workflow software",
                    "knowledge": "Core product knowledge.",
                }
            }
        },
    )
    monkeypatch.setattr(
        knowledge_module,
        "get_custom_knowledge_text",
        lambda: "product_name: Acme Pro\nAdditional notes: buyer research",
    )

    session = prospect_session.BuyerSession(
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
        session_id="prospect123",
    )

    assert session.public_config() == {
        "max_turns": 5,
        "scoring_enabled": True,
        "feedback_style": "coaching",
    }
    assert "Workflow software" in session.product_context
    assert "Core product knowledge." in session.product_context
    assert "--- BEGIN CUSTOM PROSPECT DATA ---" in session.product_context
    assert "product_name: Acme Pro" in session.product_context
    assert "Additional notes: buyer research" in session.product_context
    from core.buyer_prompt import build_system_prompt
    from core.loader import load_prospect_config

    prompt = build_system_prompt(
        load_prospect_config()["system_prompt_template"],
        persona=session.persona,
        readiness=0.5,
        product_context=session.product_context,
        behaviour_rules="",
    )
    for persona_fact in ("workflow automation", "manual reporting", "$20-$40"):
        assert prompt.count(persona_fact) == 1
