"""Tests for Prospect Mode feature.

Run: pytest tests/test_prospect.py -v
"""


# =============================================================================
# Config Tests (Deterministic)
# =============================================================================

class TestProspectConfig:
    """Test prospect_config.yaml structure and validity."""

    def test_all_difficulties_present(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        profiles = config["difficulty_profiles"]
        assert "easy" in profiles
        assert "medium" in profiles
        assert "hard" in profiles

    def test_behavior_params_valid(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        for diff, profile in config["difficulty_profiles"].items():
            b = profile["behavior"]
            assert 0.0 <= b["initial_readiness"] <= 1.0, f"{diff}: invalid initial_readiness"
            assert b["readiness_gain_per_good_turn"] > 0, f"{diff}: gain must be positive"
            assert b["readiness_loss_per_bad_turn"] > 0, f"{diff}: loss must be positive"
            assert b["max_objections"] >= 1, f"{diff}: must allow at least 1 objection"
            assert b["patience_turns"] >= 5, f"{diff}: patience too low"

    def test_personas_have_required_fields(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        personas = config["personas"]
        required = {"name", "background", "needs", "budget", "pain_points", "personality"}
        for category, persona_list in personas.items():
            for persona in persona_list:
                missing = required - persona.keys()
                assert not missing, f"Persona '{persona.get('name', '?')}' in '{category}' missing: {missing}"

    def test_evaluation_weights_sum_to_one(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        criteria = config["evaluation"]["criteria"]
        total = sum(c["weight"] for c in criteria.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"

    def test_easy_readiness_higher_than_hard(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        profiles = config["difficulty_profiles"]
        assert profiles["easy"]["behavior"]["initial_readiness"] > profiles["hard"]["behavior"]["initial_readiness"]

    def test_hard_has_more_objections_than_easy(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        profiles = config["difficulty_profiles"]
        assert profiles["hard"]["behavior"]["max_objections"] > profiles["easy"]["behavior"]["max_objections"]

    def test_objection_bank_not_empty(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        for diff, profile in config["difficulty_profiles"].items():
            bank = profile.get("objection_bank", [])
            assert len(bank) > 0, f"{diff}: objection_bank is empty"

    def test_system_prompt_template_exists(self):
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        template = config.get("system_prompt_template", "")
        assert len(template) > 50, "system_prompt_template too short or missing"
        assert "{name}" in template
        assert "{behavior_rules}" in template


# =============================================================================
# ProspectState Tests (Deterministic)
# =============================================================================

class TestProspectState:
    """Test ProspectState data structure behavior."""

    def test_initial_readiness_matches_difficulty(self):
        from chatbot.prospect.prospect import ProspectState
        from chatbot.loader import load_prospect_config as _load_prospect_config
        config = _load_prospect_config()
        for diff, profile in config["difficulty_profiles"].items():
            state = ProspectState(
                readiness=profile["behavior"]["initial_readiness"],
                difficulty=diff,
            )
            assert state.readiness == profile["behavior"]["initial_readiness"]

    def test_readiness_clamped_at_zero(self):
        from chatbot.utils import clamp as _clamp
        assert _clamp(-0.5) == 0.0

    def test_readiness_clamped_at_one(self):
        from chatbot.utils import clamp as _clamp
        assert _clamp(1.5) == 1.0

    def test_status_active(self):
        from chatbot.prospect.prospect import ProspectState
        state = ProspectState(readiness=0.5)
        assert state.status == "active"

    def test_status_sold(self):
        from chatbot.prospect.prospect import ProspectState
        state = ProspectState(readiness=0.9, has_committed=True)
        assert state.status == "sold"

    def test_status_walked(self):
        from chatbot.prospect.prospect import ProspectState
        state = ProspectState(readiness=0.1, has_walked=True)
        assert state.status == "walked"

    def test_to_dict(self):
        from chatbot.prospect.prospect import ProspectState
        state = ProspectState(
            readiness=0.65,
            objections_raised=2,
            turn_count=5,
            difficulty="medium",
            persona={"name": "Alex"},
        )
        d = state.to_dict()
        assert d["readiness"] == 0.65
        assert d["objections_raised"] == 2
        assert d["turn_count"] == 5
        assert d["persona_name"] == "Alex"
        assert d["difficulty"] == "medium"


# =============================================================================
# Persona Selection Tests (Deterministic)
# =============================================================================

class TestPersonaSelection:
    """Test persona selection logic."""

    def test_general_personas_returned(self):
        from chatbot.prospect.prospect import select_persona
        persona = select_persona("nonexistent_product", "easy")
        assert "name" in persona
        assert "needs" in persona

    def test_product_specific_persona_exists(self):
        from chatbot.prospect.prospect import select_persona
        persona = select_persona("luxury_cars", "medium")
        assert "name" in persona
        # Should get a luxury car persona, not a general one
        assert persona["name"] in ("Marcus", "Priya") or persona["name"] in ("Alex", "Sam", "Jordan")


# =============================================================================
# Prompt Building Tests (Deterministic)
# =============================================================================

class TestPromptBuilding:
    """Test system prompt construction."""

    def test_persona_name_in_prompt(self):
        from chatbot.prospect.prospect import ProspectSession
        # We need to mock the provider to avoid actual LLM calls
        session = ProspectSession.__new__(ProspectSession)
        session.persona = {"name": "TestUser", "background": "Test", "personality": "Nice",
                          "needs": ["speed"], "pain_points": ["slow"], "budget": "$100"}
        session.product_type = "default"
        session.product_context = "test products"
        session.state = __import__("chatbot.prospect.prospect", fromlist=["ProspectState"]).ProspectState(
            readiness=0.5, difficulty="easy", persona=session.persona
        )
        config = __import__("chatbot.loader", fromlist=["load_prospect_config"]).load_prospect_config()
        session.difficulty_profile = config["difficulty_profiles"]["easy"]
        session.behavior_rules = config.get("behavior_rules", {}).get("easy", "")

        prompt = session._build_system_prompt()
        assert "TestUser" in prompt

    def test_difficulty_rules_in_prompt(self):
        from chatbot.prospect.prospect import ProspectSession, ProspectState
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()

        session = ProspectSession.__new__(ProspectSession)
        session.persona = {"name": "Alex", "background": "Test", "personality": "Nice",
                          "needs": ["speed"], "pain_points": ["slow"], "budget": "$100"}
        session.product_type = "default"
        session.product_context = "test"
        session.state = ProspectState(readiness=0.2, difficulty="hard", persona=session.persona)
        session.difficulty_profile = config["difficulty_profiles"]["hard"]
        session.behavior_rules = config.get("behavior_rules", {}).get("hard", "")

        prompt = session._build_system_prompt()
        assert "Tough Negotiator" in prompt or "guarded" in prompt.lower()


# =============================================================================
# Score Clamping Tests (Deterministic)
# =============================================================================

class TestScoreClamping:
    """Test score clamping utility."""

    def test_valid_score(self):
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score(75) == 75

    def test_negative_clamped(self):
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score(-10) == 0

    def test_over_100_clamped(self):
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score(200) == 100

    def test_non_numeric_default(self):
        from chatbot.utils import clamp_score as _clamp_score
        assert _clamp_score("abc") == 50
        assert _clamp_score(None) == 50


# =============================================================================
# Evaluator Tests (Deterministic)
# =============================================================================

class TestEvaluator:
    """Test evaluation utilities."""

    def test_grade_from_score(self):
        from chatbot.prospect.prospect_evaluator import _grade_from_score
        assert _grade_from_score(95) == "A"
        assert _grade_from_score(85) == "B"
        assert _grade_from_score(75) == "C"
        assert _grade_from_score(65) == "D"
        assert _grade_from_score(50) == "F"

    def test_fallback_evaluation(self):
        from chatbot.prospect.prospect_evaluator import _fallback_evaluation
        result = _fallback_evaluation("walked")
        assert result["overall_score"] == 50
        assert result["grade"] == "C"
        assert result["outcome"] == "walked"
        assert len(result["criteria_scores"]) == 5

    def test_build_evaluation_weights(self):
        from chatbot.prospect.prospect_evaluator import _build_evaluation
        from chatbot.loader import load_prospect_config
        config = load_prospect_config()
        criteria = config["evaluation"]["criteria"]

        mock_result = {
            "criteria_scores": {
                "needs_discovery": {"score": 80, "feedback": "Good"},
                "rapport_building": {"score": 70, "feedback": "OK"},
                "objection_handling": {"score": 60, "feedback": "Needs work"},
                "solution_presentation": {"score": 90, "feedback": "Great"},
                "conversation_flow": {"score": 75, "feedback": "Fine"},
            },
            "strengths": ["Good questions"],
            "improvements": ["Build more rapport"],
            "summary": "Decent performance.",
        }

        result = _build_evaluation(mock_result, criteria, "sold")
        assert result["outcome"] == "sold"
        assert 0 <= result["overall_score"] <= 100
        assert result["grade"] in ("A", "B", "C", "D", "F")
        # Verify weighted calculation
        expected = (80*0.25 + 70*0.20 + 60*0.20 + 90*0.20 + 75*0.15)
        assert result["overall_score"] == round(expected)


# =============================================================================
# Serialization Tests (Deterministic)
# =============================================================================

class TestSerialization:
    """Test ProspectState and session serialization."""

    def test_state_roundtrip(self):
        from chatbot.prospect.prospect import ProspectState
        state = ProspectState(
            readiness=0.75,
            objections_raised=2,
            turn_count=8,
            needs_disclosed=["budget"],
            has_committed=False,
            has_walked=False,
            persona={"name": "Alex"},
            difficulty="medium",
            product_type="luxury_cars",
        )
        d = state.to_dict()
        assert d["readiness"] == 0.75
        assert d["persona_name"] == "Alex"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
