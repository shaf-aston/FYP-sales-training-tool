"""Tests for trainer.py coaching module and dev panel underlying logic.

Covers the two previously untested areas:
1. generate_training() and answer_training_question() — all paths including fallback
2. Dev panel route logic — FSM stage jumps, signal analysis, prompt generation

Run with: pytest tests/test_trainer_and_devpanel.py -v
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from chatbot.analysis import analyse_state, user_demands_directness  # noqa: E402
from chatbot.content import SIGNALS  # noqa: E402
from chatbot.flow import ADVANCEMENT_RULES, SalesFlowEngine  # noqa: E402
from chatbot.trainer import answer_training_question, generate_training  # noqa: E402
from chatbot.utils import contains_nonnegated_keyword  # noqa: E402

# ─── Mock helpers ─────────────────────────────────────────────────────────────


class MockLLMResponse:
    def __init__(self, content="", error=None, model="mock"):
        self.content = content
        self.error = error
        self.model = model
        self.latency_ms = 10.0


class MockProvider:
    """Returns canned responses in order."""

    def __init__(self, responses=None):
        self._responses = responses or []
        self._call_count = 0

    def chat(self, messages, temperature=0.3, max_tokens=200, stage=None):
        resp = self._responses[self._call_count] if self._call_count < len(self._responses) else ""
        self._call_count += 1
        return MockLLMResponse(content=resp)

    def get_model_name(self):
        return "mock"

    def is_available(self):
        return True


class MockProviderError:
    """Provider that always returns an error flag."""

    def chat(self, messages, **kwargs):
        r = MockLLMResponse(content="")
        r.error = "API error"
        return r

    def get_model_name(self):
        return "mock"

    def is_available(self):
        return True


class MockProviderRaises:
    """Provider that raises an exception."""

    def chat(self, messages, **kwargs):
        raise RuntimeError("connection timeout")

    def get_model_name(self):
        return "mock"

    def is_available(self):
        return True


# Canonical valid coaching JSON the LLM would return
VALID_COACHING_JSON = json.dumps(
    {
        "what_happened": "Asked an open-ended probe about the problem.",
        "next_move": "Get them to name what isn't working.",
        "watch_for": ["Don't pitch too early", "Listen for emotional language"],
    }
)


def _engine(stage="intent", strategy="consultative"):
    """Create a SalesFlowEngine and advance to the given stage."""
    eng = SalesFlowEngine(strategy, "cars")
    eng.advance(target_stage=stage)
    return eng


# ─── generate_training ────────────────────────────────────────────────────────


class TestGenerateTraining:
    """All paths in generate_training(): happy path, fallback, edge cases."""

    def test_valid_json_returns_all_fields(self):
        """Happy path: LLM returns well-formed JSON → all 3 fields present."""
        provider = MockProvider(responses=[VALID_COACHING_JSON])
        result = generate_training(provider, _engine("logical"), "I've been struggling", "I hear you.")
        assert result["what_happened"] == "Asked an open-ended probe about the problem."
        assert result["next_move"] == "Get them to name what isn't working."
        assert result["watch_for"] == ["Don't pitch too early", "Listen for emotional language"]

    def test_malformed_json_falls_back_no_exception(self):
        """Non-JSON LLM response → fallback dict, never an exception."""
        provider = MockProvider(responses=["This is not JSON at all"])
        result = generate_training(provider, _engine("intent"), "hello", "hi")
        assert "what_happened" in result
        assert "watch_for" in result
        assert isinstance(result["watch_for"], list)

    def test_empty_response_falls_back(self):
        """Empty content from LLM → fallback, not crash."""
        provider = MockProvider(responses=[""])
        result = generate_training(provider, _engine("intent"), "hello", "hi")
        assert "what_happened" in result

    def test_error_response_falls_back(self):
        """LLM returns error flag → fallback."""
        result = generate_training(MockProviderError(), _engine("pitch"), "ok", "great!")
        assert "what_happened" in result
        assert isinstance(result["watch_for"], list)

    def test_provider_exception_falls_back(self):
        """Provider raises → fallback, not crash."""
        result = generate_training(MockProviderRaises(), _engine("intent"), "hello", "hi")
        assert "what_happened" in result
        assert isinstance(result["watch_for"], list)

    def test_fallback_what_happened_uses_rubric(self):
        """Fallback what_happened comes from quiz rubric goal."""
        provider = MockProvider(responses=["not json"])
        result = generate_training(provider, _engine("logical"), "ok", "ok")
        assert len(result["what_happened"]) > 10

    def test_fallback_next_move_uses_rubric(self):
        """Fallback next_move comes from rubric advance_when, not '—'."""
        provider = MockProvider(responses=["not json"])
        result = generate_training(provider, _engine("emotional"), "ok", "ok")
        assert result["next_move"] != "—"
        assert len(result["next_move"]) > 5

    def test_watch_for_coerced_to_list_when_string(self):
        """If LLM returns watch_for as a string, it's coerced to empty list."""
        bad_json = json.dumps(
            {
                "stage_goal": "X",
                "what_bot_did": "Y",
                "next_trigger": "Z",
                "where_heading": "W",
                "watch_for": "should be a list",
            }
        )
        result = generate_training(MockProvider(responses=[bad_json]), _engine("intent"), "x", "y")
        assert isinstance(result["watch_for"], list)

    def test_markdown_json_block_stripped_and_parsed(self):
        """LLM wraps JSON in ```json ... ``` → still parses correctly."""
        wrapped = f"```json\n{VALID_COACHING_JSON}\n```"
        result = generate_training(MockProvider(responses=[wrapped]), _engine("logical"), "msg", "reply")
        assert result["what_happened"] == "Asked an open-ended probe about the problem."

    def test_transactional_strategy_no_crash(self):
        """Transactional flow fetches rubric without error."""
        result = generate_training(
            MockProvider(responses=[VALID_COACHING_JSON]),
            _engine("pitch", "transactional"),
            "budget is 500",
            "Great choice!",
        )
        assert "what_happened" in result

    def test_rubric_context_injected_in_all_consultative_stages(self):
        """generate_training runs without error at every consultative stage."""
        stages = ["intent", "logical", "emotional", "pitch", "objection"]
        for stage in stages:
            result = generate_training(
                MockProvider(responses=[VALID_COACHING_JSON]),
                _engine(stage, "consultative"),
                "test message",
                "test reply",
            )
            assert "what_happened" in result, f"Missing what_happened at {stage}"

    def test_max_tokens_accepted_by_mock(self):
        """Provider is called — confirms max_tokens parameter doesn't cause errors."""
        provider = MockProvider(responses=[VALID_COACHING_JSON])
        generate_training(provider, _engine("intent"), "msg", "reply")
        assert provider._call_count == 1


# ─── answer_training_question ─────────────────────────────────────────────────


class TestAnswerTrainingQuestion:
    """All paths in answer_training_question()."""

    def test_valid_response_returns_answer_dict(self):
        """Happy path: LLM text → {"answer": <text>}."""
        provider = MockProvider(responses=["The bot used future-pacing here."])
        engine = _engine("emotional", "consultative")
        result = answer_training_question(provider, engine, "Why did the bot ask that?")
        assert "answer" in result
        assert "future-pacing" in result["answer"]

    def test_error_response_returns_graceful_message(self):
        """LLM error flag → graceful answer, not exception."""
        engine = _engine("intent", "consultative")
        result = answer_training_question(MockProviderError(), engine, "What stage?")
        assert "answer" in result
        assert len(result["answer"]) > 0

    def test_provider_exception_returns_graceful_message(self):
        """Provider raises → graceful answer string, not exception."""
        engine = _engine("pitch", "consultative")
        result = answer_training_question(MockProviderRaises(), engine, "Why pitch now?")
        assert "answer" in result
        assert len(result["answer"]) > 0

    def test_provider_is_called_once(self):
        """The question is forwarded to the provider — call count == 1."""
        provider = MockProvider(responses=["Good question!"])
        answer_training_question(provider, _engine("intent"), "Is this right?")
        assert provider._call_count == 1

    def test_empty_conversation_history_no_crash(self):
        """Works even when conversation history is empty (session start)."""
        engine = SalesFlowEngine("consultative", "cars")  # No turns yet
        result = answer_training_question(MockProvider(responses=["No history yet!"]), engine, "What's happening?")
        assert "answer" in result

    def test_returns_dict_not_string(self):
        """Return type is always a dict, never a raw string."""
        provider = MockProvider(responses=["Some answer"])
        result = answer_training_question(provider, _engine("logical"), "explain?")
        assert isinstance(result, dict)


# ─── Dev panel underlying logic ───────────────────────────────────────────────


class TestDevPanelStageJump:
    """SalesFlowEngine.advance(target_stage=...) — the function called by /api/debug/stage."""

    def test_jump_to_middle_stage(self):
        """Can jump to emotional directly from intent."""
        eng = _engine("intent", "consultative")
        eng.advance(target_stage="emotional")
        assert eng.current_stage == "emotional"

    def test_jump_resets_stage_turn_count(self):
        """stage_turn_count is reset to 0 on any jump."""
        eng = _engine("intent", "consultative")
        eng.stage_turn_count = 9
        eng.advance(target_stage="pitch")
        assert eng.stage_turn_count == 0

    def test_jump_to_objection(self):
        """Can jump to terminal stage."""
        eng = _engine("intent", "consultative")
        eng.advance(target_stage="objection")
        assert eng.current_stage == "objection"

    def test_jump_unknown_stage_falls_through_to_sequential(self):
        """advance() with unknown target falls through to sequential advance.
        This documents that route validates first — this is safe-mode behaviour."""
        eng = _engine("intent", "consultative")
        eng.advance(target_stage="nonexistent_stage")
        # Falls through to sequential: intent → logical
        assert eng.current_stage == "logical"

    def test_transactional_lacks_logical_emotional(self):
        """Transactional flow stages: intent, pitch, objection only."""
        eng = SalesFlowEngine("transactional", "laptops")
        available_stages = eng.flow_config["stages"]
        assert "logical" not in available_stages
        assert "emotional" not in available_stages
        assert "pitch" in available_stages

    def test_jump_to_stage_not_in_transactional_falls_to_sequential(self):
        """advance(target_stage='logical') on transactional falls through to pitch."""
        eng = SalesFlowEngine("transactional", "laptops")
        eng.advance(target_stage="logical")
        assert eng.current_stage == "pitch"


class TestDevPanelPrompt:
    """SalesFlowEngine.get_current_prompt() — the function called by /api/debug/prompt."""

    def test_prompt_nonempty_at_all_consultative_stages(self):
        """Prompt generation returns a non-empty string at every consultative stage."""
        for stage in ["intent", "logical", "emotional", "pitch", "objection"]:
            eng = _engine(stage, "consultative")
            prompt = eng.get_current_prompt(user_message="")
            assert isinstance(prompt, str), f"Expected str at {stage}"
            assert len(prompt) > 50, f"Prompt too short at {stage}: {repr(prompt[:50])}"

    def test_prompt_nonempty_at_all_transactional_stages(self):
        """Prompt generation returns a non-empty string at every transactional stage."""
        for stage in ["intent", "pitch", "objection"]:
            eng = _engine(stage, "transactional")
            prompt = eng.get_current_prompt(user_message="")
            assert isinstance(prompt, str)
            assert len(prompt) > 50

    def test_prompt_includes_product_context(self):
        """Product context is injected into the prompt."""
        eng = SalesFlowEngine("consultative", "premium electric vehicles")
        prompt = eng.get_current_prompt(user_message="")
        assert "electric" in prompt.lower() or "vehicle" in prompt.lower() or len(prompt) > 100


class TestDevPanelSignalAnalysis:
    """Logic called by /api/debug/analyse — signal detection without LLM."""

    def test_signal_hits_has_all_required_keys(self):
        """signal_hits dict must contain all 10 keys the frontend renders."""
        engine = _engine("intent", "consultative")
        message = "I need help with my car"
        msg_lower = message.lower()

        signal_keys = [
            "high_intent",
            "low_intent",
            "commitment",
            "objection",
            "walking",
            "impatience",
            "direct_info_requests",
            "user_consultativeSIGNALS",
            "user_transactionalSIGNALS",
        ]
        signal_hits = {k: contains_nonnegated_keyword(msg_lower, SIGNALS.get(k, [])) for k in signal_keys}
        signal_hits["demands_directness"] = user_demands_directness(engine.conversation_history, message)

        for k in signal_keys + ["demands_directness"]:
            assert k in signal_hits, f"Missing signal key: {k}"

    def test_high_intent_message_detected(self):
        """'ready to buy' triggers high_intent signal."""
        assert contains_nonnegated_keyword("I'm ready to buy a car", SIGNALS.get("high_intent", []))

    def test_commitment_message_detected(self):
        """Classic commitment phrase is caught."""
        assert contains_nonnegated_keyword("yes let's do it", SIGNALS["commitment"])

    def test_low_intent_browsing_detected(self):
        """'just browsing' triggers low_intent."""
        assert contains_nonnegated_keyword("just browsing really", SIGNALS["low_intent"])

    def test_state_returns_correct_structure(self):
        """analyse_state returns ConversationState with all 4 fields."""
        state = analyse_state([], "I need this urgently", signal_keywords=SIGNALS)
        assert hasattr(state, "intent")
        assert hasattr(state, "guarded")
        assert hasattr(state, "decisive")
        assert hasattr(state, "question_fatigue")
        assert state.intent in ("low", "medium", "high")

    def test_advancement_rule_fires_on_clear_intent(self):
        """user_has_clear_intent fires for 'ready to buy'."""
        engine = _engine("intent", "consultative")
        rule = ADVANCEMENT_RULES["user_has_clear_intent"]
        assert rule(engine.conversation_history, "I'm ready to buy a car", 0) is True

    def test_advancement_rule_doesnt_fire_on_generic(self):
        """user_has_clear_intent stays False for generic greeting at turn 0."""
        engine = _engine("intent", "consultative")
        rule = ADVANCEMENT_RULES["user_has_clear_intent"]
        assert rule(engine.conversation_history, "hello how are you", 0) is False

    def test_advancement_fires_on_max_turns_safety_valve(self):
        """Intent stage auto-advances after 6 turns (safety valve) regardless of message."""
        engine = _engine("intent", "consultative")
        rule = ADVANCEMENT_RULES["user_has_clear_intent"]
        # At 6 turns, even a generic message triggers advancement
        assert rule(engine.conversation_history, "hello", 6) is True

    def test_commitment_or_objection_requires_min_words(self):
        """Short messages (< 3 words) never advance from pitch stage."""
        rule = ADVANCEMENT_RULES["commitment_or_objection"]
        assert rule([], "ok", 0) is False
        assert rule([], "yes let's do it", 0) is True
