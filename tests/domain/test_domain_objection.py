"""Tests for Sales Sniper Objection Handling Matrix SOP implementation.

Verifies:
1. classify_objection() correctly identifies each of the 6 types
2. Returned guidance matches SOP-aligned language
3. _get_stage_specific_prompt() injects SOP steps for each type

Run: pytest tests/test_objection_sop.py -v
"""

import pytest

from chatbot.objection import classify_objection
from chatbot.content import SOP_FLOWS, _get_stage_specific_prompt

# --- Canonical trigger phrases per type ---
_TRIGGER_PHRASES = {
    "money": "I can't afford it, it's too expensive for me",
    "partner": "I need to check with my wife first before deciding",
    "fear": "I'm worried it might not work and I'd regret it",
    "think": "Let me think about it and sleep on it",
    "logistical": "Not sure about the timing and the whole setup process",
    "smokescreen": "Not interested, I'm good thanks, not for me",
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
        assert "funding" in SOP_FLOWS["money"].lower()

    def test_partner_contains_same_side(self):
        assert (
            "same side" in SOP_FLOWS["partner"].lower()
            or "on board" in SOP_FLOWS["partner"].lower()
        )

    def test_fear_contains_perspective_shift(self):
        assert "decision" in SOP_FLOWS["fear"].lower()

    def test_think_addresses_logistical_first(self):
        assert (
            "investment" in SOP_FLOWS["think"].lower()
            or "logistical" in SOP_FLOWS["think"].lower()
        )

    def test_smokescreen_tests_legitimacy(self):
        assert (
            "genuine" in SOP_FLOWS["smokescreen"].lower()
            or "product itself" in SOP_FLOWS["smokescreen"].lower()
        )


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
        assert obj_type.upper() in context, (
            f"Type {obj_type} not in context for: {phrase}"
        )

    @pytest.mark.parametrize("obj_type,phrase", list(_REFRAMEABLE.items()))
    def test_context_contains_sop_steps(self, obj_type, phrase):
        context = self._run(phrase)
        assert "STEPS:" in context
        assert context.count("\n") >= 3

    def test_smokescreen_returns_empty_context(self):
        # Smokescreen phrases trigger walkaway guard → no reframe injected (correct SOP behaviour)
        context = self._run(_TRIGGER_PHRASES["smokescreen"])
        assert context == ""


class TestObjectionIsolation:
    """Objection context must stay isolated to objection stage."""

    class _FakeState:
        intent = "high"

    def test_non_objection_stage_does_not_call_objection_builder(self, monkeypatch):
        import chatbot.content as content_mod

        def _boom(*args, **kwargs):
            raise AssertionError(
                "objection builder should not run outside objection stage"
            )

        monkeypatch.setattr(content_mod, "_build_objection_context", _boom)

        prompt, context = content_mod._get_stage_specific_prompt(
            strategy="consultative",
            stage="logical",
            state=self._FakeState(),
            user_message="I am still figuring this out",
            history=[{"role": "user", "content": "I am still figuring this out"}],
        )

        assert prompt
        assert context == ""


# ============================================================================
# NEW PATHWAY TESTS (Phase 0): Framework alignment verification
# ============================================================================


class TestPathwayAnalysis:
    """Verify ObjectionPathway structure and enriched metadata."""

    def test_analyze_objection_pathway_returns_dict_with_base_keys(self):
        """analyze_objection_pathway wraps classify_objection; must have base 3 keys."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I can't afford it")

        # Base keys always present
        assert "type" in pathway
        assert "strategy" in pathway
        assert "guidance" in pathway
        assert pathway["type"] in ["money", "unknown"]

    def test_analyze_objection_pathway_returns_pathway_keys(self):
        """analyze_objection_pathway adds new pathway keys."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I can't afford it")

        # New pathway keys
        assert "category" in pathway
        assert "subtype" in pathway
        assert "entry_question" in pathway
        assert "reframes" in pathway
        assert "funding_options" in pathway
        assert "open_wallet_applicable" in pathway

    def test_pathway_keys_are_populated_for_money(self):
        """Money objection returns populated pathway structure."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("It's too expensive")

        assert pathway.get("category") == "resource"
        assert pathway.get("entry_question")
        assert len(pathway.get("entry_question", "")) > 0
        assert pathway.get("reframes")
        assert len(pathway.get("reframes", [])) > 0
        assert pathway.get("open_wallet_applicable") is True

    def test_pathway_keys_populated_for_partner(self):
        """Partner objection returns stakeholder pathway."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I need to check with my husband")

        assert pathway.get("category") == "stakeholder"
        assert pathway.get("entry_question")
        assert pathway.get("open_wallet_applicable") is True
        assert pathway.get("funding_options") == []  # No funding for stakeholder

    def test_reframe_descriptions_present_for_resource(self):
        """Reframe descriptions include dialogue and examples."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I don't have the money")

        reframe_descs = pathway.get("reframe_descriptions", {})
        assert len(reframe_descs) > 0

        for reframe_id, desc in reframe_descs.items():
            assert "title" in desc
            assert "dialogue" in desc
            assert "example" in desc
            assert "check_question" in desc
            assert len(desc["dialogue"]) > 0


class TestReframeSequencing:
    """Verify reframe sequence R1→R2→R3 ordering."""

    def test_get_reframe_sequence_returns_correct_structure(self):
        """get_reframe_sequence returns dict with sequence info."""
        from chatbot.objection import analyze_objection_pathway, get_reframe_sequence

        pathway = analyze_objection_pathway("I need to think about it")
        seq = get_reframe_sequence(pathway, current_turn_in_stage=0, history=[])

        assert "current_reframe" in seq
        assert "reframe_index" in seq
        assert "attempts_so_far" in seq
        assert "next_check_question" in seq
        assert "is_final_reframe" in seq

    def test_first_reframe_is_change_of_process(self):
        """First reframe in sequence should be change_of_process (R1)."""
        from chatbot.objection import analyze_objection_pathway, get_reframe_sequence

        pathway = analyze_objection_pathway("I need to think about it")
        seq = get_reframe_sequence(pathway, current_turn_in_stage=0, history=[])

        assert seq["current_reframe"] == "change_of_process"
        assert seq["reframe_index"] == 0
        assert seq["is_final_reframe"] is False

    def test_reframe_sequence_with_prior_attempts(self):
        """Track reframe attempts via history markers."""
        from chatbot.objection import analyze_objection_pathway, get_reframe_sequence

        pathway = analyze_objection_pathway("I'm worried")

        # Simulate first reframe already attempted
        history = [
            {"role": "assistant", "content": "reframe_change_of_process something"},
            {"role": "user", "content": "yes I see"},
        ]

        seq = get_reframe_sequence(pathway, current_turn_in_stage=1, history=history)

        # Should advance to next reframe
        assert seq["current_reframe"] == "island_mountain"
        assert seq["reframe_index"] == 1

    def test_reframe_check_question_populated(self):
        """Each reframe has a check question."""
        from chatbot.objection import analyze_objection_pathway, get_reframe_sequence

        pathway = analyze_objection_pathway("I need to think about it")
        seq = get_reframe_sequence(pathway, current_turn_in_stage=0, history=[])

        check_q = seq.get("next_check_question", "")
        assert len(check_q) > 0
        assert "?" in check_q


class TestBackwardCompatibility:
    """Verify old classify_objection() still works unchanged."""

    def test_classify_objection_unchanged(self):
        """classify_objection returns same 3-key dict as before."""
        result = classify_objection("I can't afford it")

        assert result["type"] == "money"
        assert "strategy" in result
        assert "guidance" in result
        assert len(result) == 3  # Only 3 keys, no new ones

    def test_existing_objection_tests_pass(self):
        """All existing TestClassifyObjection tests still pass."""
        for obj_type, phrase in _TRIGGER_PHRASES.items():
            result = classify_objection(phrase)
            assert result["type"] == obj_type
            assert result["guidance"]

    def test_analyze_pathway_includes_base_keys(self):
        """analyze_objection_pathway returns all base keys."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I can't afford it")

        # Old code can still call .get("type") and it works
        assert pathway.get("type") == "money"
        assert pathway.get("strategy")
        assert pathway.get("guidance")


class TestResourceVsStakeholder:
    """Verify Resource/Stakeholder category split."""

    @pytest.mark.parametrize(
        "phrase,expected_category",
        [
            ("I can't afford it", "resource"),
            ("It's too expensive", "resource"),
            ("Need to check with my husband", "stakeholder"),
            ("Partner needs to approve", "stakeholder"),
        ],
    )
    def test_category_classification(self, phrase, expected_category):
        """Money/partner objections classified to resource/stakeholder."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway(phrase)
        assert pathway.get("category") == expected_category

    def test_resource_has_funding_options(self):
        """Resource pathway includes funding options list."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("Too expensive, can't afford it")

        funding_opts = pathway.get("funding_options", [])
        assert len(funding_opts) > 0
        assert "savings" in funding_opts or any(
            "credit" in opt.lower() for opt in funding_opts
        )

    def test_stakeholder_has_no_funding_options(self):
        """Stakeholder pathway has empty funding options."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("My wife needs to decide")

        assert pathway.get("funding_options") == []

    def test_resource_subtype_detection(self):
        """Detect specific funding subtype."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I can't afford the price")

        subtype = pathway.get("subtype", "")
        assert len(subtype) > 0
        assert subtype in ["funding", "staged_payment", "unspecified"]


class TestEntryQuestions:
    """Verify type-specific entry questions."""

    def test_resource_entry_question_includes_budget(self):
        """Resource entry question asks about budget."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("Too expensive")

        entry_q = pathway.get("entry_question", "")
        assert "budget" in entry_q.lower() or "funds" in entry_q.lower()

    def test_stakeholder_entry_question_asks_independent(self):
        """Stakeholder entry question asks about independence."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("My spouse needs to agree")

        entry_q = pathway.get("entry_question", "")
        assert "independent" in entry_q.lower() or "you" in entry_q.lower()

    def test_internal_entry_question_asks_about_decision_making(self):
        """Internal (fear) entry question asks about decision-making."""
        from chatbot.objection import analyze_objection_pathway

        pathway = analyze_objection_pathway("I need to think about it")

        entry_q = pathway.get("entry_question", "")
        assert "decision" in entry_q.lower() or "think" in entry_q.lower()

    def test_entry_questions_differ_by_category(self):
        """Entry questions are unique per category."""
        from chatbot.objection import analyze_objection_pathway

        resource_pw = analyze_objection_pathway("Can't afford it")
        stakeholder_pw = analyze_objection_pathway("Partner needs approval")
        internal_pw = analyze_objection_pathway("Let me think about it")

        resource_q = resource_pw.get("entry_question", "")
        stakeholder_q = stakeholder_pw.get("entry_question", "")
        internal_q = internal_pw.get("entry_question", "")

        # All three should be different
        assert resource_q != stakeholder_q
        assert stakeholder_q != internal_q
        assert resource_q != internal_q
