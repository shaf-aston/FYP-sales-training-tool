"""Tests for FSM flow hardening and state machine correctness."""
import pytest

import core.flow as flow
from core.flow import SalesFlowEngine, _check_advancement_condition, _commitment_or_objection
from core.utils import Stage, Strategy


def test_short_high_signal_objection_is_not_filtered(monkeypatch):
    monkeypatch.setattr(flow, "SIGNALS", {"objection": ["too expensive"]})

    assert _commitment_or_objection([], "Too expensive", 1) is True


def test_commitment_or_objection_handles_missing_signal_keys(monkeypatch):
    monkeypatch.setattr(flow, "SIGNALS", {})

    assert _commitment_or_objection([], "hello there", 1) is False


def test_advancement_condition_uses_current_user_message_when_history_lags(monkeypatch):
    monkeypatch.setattr(
        flow,
        "ANALYSIS_CONFIG",
        {
            "advancement": {
                "logical": {"doubt_keywords": ["confused"], "max_turns": 10}
            }
        },
    )

    assert _check_advancement_condition([], "I am confused", 2, "logical", min_turns=2) is True


def test_advance_rejects_invalid_target_stage():
    engine = SalesFlowEngine(Strategy.CONSULTATIVE, "test product")

    with pytest.raises(ValueError, match="Target stage"):
        engine.advance(target_stage="not-a-stage")


def test_restore_state_rejects_invalid_flow_type():
    engine = SalesFlowEngine(Strategy.CONSULTATIVE, "test product")

    with pytest.raises(ValueError, match="Invalid flow_type"):
        engine.restore_state(
            {
                "flow_type": "legacy-flow",
                "current_stage": Stage.LOGICAL,
                "stage_turn_count": 1,
            }
        )


def test_restore_state_rejects_stage_not_in_flow():
    engine = SalesFlowEngine(Strategy.TRANSACTIONAL, "test product")

    with pytest.raises(ValueError, match="Invalid current_stage"):
        engine.restore_state(
            {
                "flow_type": Strategy.TRANSACTIONAL,
                "current_stage": Stage.LOGICAL,
                "stage_turn_count": 1,
            }
        )


def test_common_transitions_are_not_shared_between_flows():
    consultative_pitch = flow.FLOWS[Strategy.CONSULTATIVE]["transitions"][Stage.PITCH]
    transactional_pitch = flow.FLOWS[Strategy.TRANSACTIONAL]["transitions"][Stage.PITCH]

    assert consultative_pitch is not transactional_pitch


def test_transactional_flow_includes_negotiation_stage():
    assert flow.FLOWS[Strategy.TRANSACTIONAL]["stages"] == [
        Stage.INTENT,
        Stage.PITCH,
        Stage.NEGOTIATION,
        Stage.OBJECTION,
        Stage.OUTCOME,
    ]
    assert flow.FLOWS[Strategy.TRANSACTIONAL]["transitions"][Stage.PITCH]["next"] == Stage.NEGOTIATION
    assert flow.FLOWS[Strategy.TRANSACTIONAL]["transitions"][Stage.NEGOTIATION]["next"] == Stage.OBJECTION


def test_commitment_or_walkaway_rule_signature_matches_fsm_contract():
    assert flow.commitment_or_walkaway([], "not now", 1) in {True, False}


def test_get_advance_target_uses_guard_mapping(monkeypatch):
    engine = SalesFlowEngine(Strategy.CONSULTATIVE, "test product")
    engine.current_stage = Stage.LOGICAL
    engine.stage_turn_count = 2
    engine.conversation_history = [{"role": "user", "content": "I am confused"}]

    monkeypatch.setattr(
        flow,
        "ANALYSIS_CONFIG",
        {
            "advancement": {
                "logical": {"doubt_keywords": ["confused"], "max_turns": 10},
                "emotional": {"stakes_keywords": ["costing"], "max_turns": 10},
            }
        },
    )

    assert engine.get_advance_target("I am confused") == Stage.EMOTIONAL


def test_turn_cap_forces_progress_when_signal_never_appears(monkeypatch):
    monkeypatch.setattr(
        flow,
        "ANALYSIS_CONFIG",
        {
            "advancement": {
                "logical": {"doubt_keywords": ["confused"], "max_turns": 3}
            }
        },
    )

    assert _check_advancement_condition([], "still not saying it", 3, "logical", min_turns=2) is True


def test_intent_strategy_switches_to_transactional_for_budget_signal(monkeypatch):
    monkeypatch.setattr(
        flow,
        "ANALYSIS_CONFIG",
        {
            "preference_keywords": {"budget": ["budget"]},
            "advancement": {
                "logical": {"doubt_keywords": ["confused"], "max_turns": 10},
                "emotional": {"stakes_keywords": ["costing"], "max_turns": 10},
            },
        },
    )
    monkeypatch.setattr(
        flow,
        "SIGNALS",
        {
            "demand_directness": [],
            "direct_info_requests": [],
            "high_intent": [],
            "low_intent": [],
            "signal_priority": ["high_intent", "low_intent"],
        },
    )
    monkeypatch.setattr(flow, "USER_CONSULTATIVE_SIGNALS", [])
    monkeypatch.setattr(flow, "USER_TRANSACTIONAL_SIGNALS", [])

    engine = SalesFlowEngine(Strategy.INTENT, "test product")

    assert engine.evaluate_strategy_switch("My budget is 500 a month") is True
    assert engine.flow_type == Strategy.TRANSACTIONAL
    assert engine.current_stage == Stage.INTENT


def test_directness_override_does_not_regress_from_objection_to_pitch(monkeypatch):
    monkeypatch.setattr(
        flow,
        "SIGNALS",
        {
            "commitment": [],
            "direct_info_requests": ["price"],
            "impatience": [],
        },
    )
    monkeypatch.setattr(flow, "user_demands_directness", lambda *_args: False)

    engine = SalesFlowEngine(Strategy.CONSULTATIVE, "test product")
    engine.current_stage = Stage.OBJECTION

    assert engine.should_advance("What's the price?") is None


def test_consultative_logical_does_not_jump_to_pitch_on_price_request(monkeypatch):
    monkeypatch.setattr(
        flow,
        "SIGNALS",
        {
            "commitment": [],
            "direct_info_requests": ["price"],
            "impatience": ["now"],
        },
    )
    monkeypatch.setattr(flow, "user_demands_directness", lambda *_args: True)

    engine = SalesFlowEngine(Strategy.CONSULTATIVE, "test product")
    engine.current_stage = Stage.LOGICAL

    assert engine.should_advance("What's the price now?") is None


def test_transactional_pitch_advances_to_negotiation_on_terms_request(monkeypatch):
    monkeypatch.setattr(
        flow,
        "SIGNALS",
        {
            "commitment": [],
            "objection": [],
            "walking": [],
            "impatience": [],
            "demand_directness": [],
            "direct_info_requests": ["how much"],
            "high_intent": [],
            "low_intent": [],
            "signal_priority": ["high_intent", "low_intent"],
            "user_transactionalSIGNALS": [],
        },
    )
    monkeypatch.setattr(
        flow,
        "ANALYSIS_CONFIG",
        {
            "advancement": {
                "negotiation": {"terms_keywords": ["how much"], "max_turns": 8},
            },
            "preference_keywords": {"budget": ["budget"]},
        },
    )

    engine = SalesFlowEngine(Strategy.TRANSACTIONAL, "test product")
    engine.current_stage = Stage.PITCH
    engine.stage_turn_count = 1

    assert engine.should_advance("How much is it?") == Stage.NEGOTIATION


def test_commitment_at_pitch_advances_directly_to_outcome():
    engine = SalesFlowEngine(Strategy.CONSULTATIVE, "test product")
    engine.current_stage = Stage.PITCH

    assert engine.should_advance("Let's go") == Stage.OUTCOME


def test_commitment_at_negotiation_advances_directly_to_outcome():
    engine = SalesFlowEngine(Strategy.TRANSACTIONAL, "test product")
    engine.current_stage = Stage.NEGOTIATION

    assert engine.should_advance("Let's go") == Stage.OUTCOME
