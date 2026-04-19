import pytest
from src.chatbot.objection import (
    classify_objection,
    analyze_objection_pathway,
    _get_objection_pathway_safe,
    _build_objection_context
)
from src.chatbot.utils import Stage, Strategy

class TestObjectionClassification:
    def test_classify_objection_money(self):
        result = classify_objection("I don't have the budget for this right now.")
        assert result["type"] == "money"
        assert "strategy" in result
        assert "guidance" in result

    def test_classify_objection_partner(self):
        result = classify_objection("I need to speak with my wife first.")
        assert result["type"] == "partner"

    def test_classify_objection_unknown_fallback(self):
        result = classify_objection("The weather is nice today.")
        assert result["type"] == "unknown"
        assert result["strategy"] == "general_reframe"

    def test_classify_objection_uses_history(self):
        history = [
            {"role": "user", "content": "I need to talk to my spouse"},
            {"role": "assistant", "content": "I understand."},
        ]
        result = classify_objection("let me think about it", history=history)
        assert result["type"] == "partner"

class TestObjectionPathwayAnalysis:
    def test_analyze_objection_pathway_structure(self):
        result = analyze_objection_pathway("This is too expensive")
        assert result["type"] == "money"
        assert "category" in result
        assert "entry_question" in result
        assert isinstance(result["reframes"], list)
        assert "funding_options" in result

    def test_analyze_objection_pathway_resource_mapping(self):
        result = analyze_objection_pathway("I don't have the budget for this right now.")
        assert result["category"] == "resource"
        assert isinstance(result["funding_options"], list)
        assert result["open_wallet_applicable"] is True

class TestObjectionPathwaySafe:
    def test_get_objection_pathway_safe_success(self):
        result = _get_objection_pathway_safe("too expensive", [])
        assert result["type"] == "money"
        assert "category" in result

class TestBuildObjectionContext:
    def test_build_objection_context_wrong_stage(self):
        # Should return empty string if stage is not OBJECTION
        context = _build_objection_context(Strategy.CONSULTATIVE, Stage.PITCH, "too expensive", [])
        assert context == ""

    def test_build_objection_context_walkaway_override(self):
        # Walkaway keywords clear the objection context entirely
        context = _build_objection_context(
            Strategy.CONSULTATIVE, 
            Stage.OBJECTION, 
            "I am definitely not interested bye", 
            []
        )
        assert context == ""

    def test_build_objection_context_success(self):
        objection_data = analyze_objection_pathway("Too expensive")
        context = _build_objection_context(
            Strategy.CONSULTATIVE, 
            Stage.OBJECTION, 
            "Too expensive", 
            [], 
            objection_data=objection_data
        )
        assert "OBJECTION CLASSIFIED: MONEY" in context
        assert "BARRIER CATEGORY: RESOURCE" in context
        assert "REFRAME SEQUENCE:" in context
