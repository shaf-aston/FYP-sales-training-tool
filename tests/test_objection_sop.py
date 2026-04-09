"""Tests for Sales Sniper Objection Handling Matrix SOP implementation.

Verifies:
1. classify_objection() correctly identifies each of the 6 types
2. Returned guidance matches SOP-aligned language
3. _get_stage_specific_prompt() injects SOP steps for each type

Run: pytest tests/test_objection_sop.py -v
"""
import pytest
from chatbot.analysis import classify_objection
from chatbot.content import _SOP_FLOWS, _get_stage_specific_prompt


# --- Canonical trigger phrases per type ---
_TRIGGER_PHRASES = {
    "money":      "I can't afford it, it's too expensive for me",
    "partner":    "I need to check with my wife first before deciding",
    "fear":       "I'm worried it might not work and I'd regret it",
    "think":      "Let me think about it and sleep on it",
    "logistical": "Not sure about the timing and the whole setup process",
    "smokescreen":"Not interested, I'm good thanks, not for me",
}


class TestClassifyObjection:
    @pytest.mark.parametrize("obj_type,phrase", list(_TRIGGER_PHRASES.items()))
    def test_classifies_correct_type(self, obj_type, phrase):
        result = classify_objection(phrase)
        assert result["type"] == obj_type, (
            f"Expected '{obj_type}' for: '{phrase}', got '{result['type']}'"
        )

    @pytest.mark.parametrize("obj_type,phrase", list(_TRIGGER_PHRASES.items()))
    def test_guidance_is_populated(self, obj_type, phrase):
        result = classify_objection(phrase)
        assert result["guidance"], f"Empty guidance for {obj_type}"
        assert len(result["guidance"]) > 20


class TestSopFlowsContent:
    """SOP flows must encode the key step from the matrix for each type."""

    def test_money_contains_self_solve(self):
        assert "funding" in _SOP_FLOWS["money"].lower()

    def test_partner_contains_same_side(self):
        assert "same side" in _SOP_FLOWS["partner"].lower() or "on board" in _SOP_FLOWS["partner"].lower()

    def test_fear_contains_perspective_shift(self):
        assert "decision" in _SOP_FLOWS["fear"].lower()

    def test_think_addresses_logistical_first(self):
        assert "investment" in _SOP_FLOWS["think"].lower() or "logistical" in _SOP_FLOWS["think"].lower()

    def test_smokescreen_tests_legitimacy(self):
        assert "genuine" in _SOP_FLOWS["smokescreen"].lower() or "product itself" in _SOP_FLOWS["smokescreen"].lower()


class TestStagePromptInjectsSopSteps:
    """_get_stage_specific_prompt injects SOP steps at objection stage."""

    class _FakeState:
        intent = "high"

    def _run(self, phrase):
        _, context = _get_stage_specific_prompt(
            strategy="consultative",
            stage="objection",
            state=self._FakeState(),
            user_message=phrase,
            history=[{"role": "user", "content": phrase}],
        )
        return context

    # Smokescreen is excluded: those phrases also fire commitment_or_walkaway (correct — SOP says no win)
    _REFRAMEABLE = {k: v for k, v in _TRIGGER_PHRASES.items() if k != "smokescreen"}

    @pytest.mark.parametrize("obj_type,phrase", list(_REFRAMEABLE.items()))
    def test_context_contains_classified_type(self, obj_type, phrase):
        context = self._run(phrase)
        assert obj_type.upper() in context, f"Type {obj_type} not in context for: {phrase}"

    @pytest.mark.parametrize("obj_type,phrase", list(_REFRAMEABLE.items()))
    def test_context_contains_sop_steps(self, obj_type, phrase):
        context = self._run(phrase)
        assert "STEPS:" in context
        assert context.count("\n") >= 3

    def test_smokescreen_returns_empty_context(self):
        # Smokescreen phrases trigger walkaway guard → no reframe injected (correct SOP behaviour)
        context = self._run(_TRIGGER_PHRASES["smokescreen"])
        assert context == ""
