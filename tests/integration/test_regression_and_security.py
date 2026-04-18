"""Regression, security, and invariant tests for the Sales Roleplay Chatbot.

Test Design Approach (based on systematic audit of 20 P0–P3 bug fixes):
- Persona  : Each test class acts as a specialist (NLP, FSM, Security, Config)
- Context  : Every class documents the exact fix it guards and the bug mode if reverted
- Format   : AAA (Arrange-Act-Assert) throughout; class-per-fix grouping
- CoT      : Complex tests reason step-by-step inside the docstring
- Adversarial: Security section treats the app as an attacker would

Run with: pytest tests/test_regression_and_security.py -v
"""

import importlib.util
import json
import os
import sys
import tempfile
import types

import pytest

from chatbot.analysis import analyse_state
from chatbot.analytics.performance import MAX_METRICS_LINES, PerformanceTracker
from chatbot.chatbot import SalesChatbot
from chatbot.flow import (
    COMMON_TRANSITIONS,
    FLOWS,
    SalesFlowEngine,
    _check_advancement_condition,
    _user_expressed_stakes,
    _user_shows_doubt,
)
from chatbot.loader import load_analysis_config
from chatbot.prompts import get_base_rules

os.environ.pop("ENABLE_DEBUG_PANEL", None)  # Ensure debug panel OFF for all tests


def _load_web_app():
    """Load src/web/app.py as 'web.app' so relative imports (from .security) work.

    app.py uses `from .security import (...)` — a relative import that requires
    the module to be loaded as a package member.  Without this setup, importing
    app.py as a top-level module raises:
        ImportError: attempted relative import with no known parent package

    Fix: register a synthetic 'web' package in sys.modules, pre-load
    web.security, then exec app.py under the web package namespace.
    """
    if "web.app" in sys.modules:
        return sys.modules["web.app"]

    src_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "src")
    )
    web_dir = os.path.join(src_dir, "web")

    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # Synthetic 'web' package (no __init__.py needed)
    if "web" not in sys.modules:
        web_pkg = types.ModuleType("web")
        web_pkg.__path__ = [web_dir]
        web_pkg.__package__ = "web"
        sys.modules["web"] = web_pkg

    # Load web.security first — app.py does `from .security import (...)`
    if "web.security" not in sys.modules:
        sec_spec = importlib.util.spec_from_file_location(
            "web.security", os.path.join(web_dir, "security.py")
        )
        assert sec_spec is not None  # Type narrowing: file must exist
        sec_mod = importlib.util.module_from_spec(sec_spec)
        sec_mod.__package__ = "web"
        sys.modules["web.security"] = sec_mod
        sec_spec.loader.exec_module(sec_mod)

    # Load app.py as web.app
    app_spec = importlib.util.spec_from_file_location(
        "web.app", os.path.join(web_dir, "app.py")
    )
    assert app_spec is not None  # Type narrowing: file must exist
    app_mod = importlib.util.module_from_spec(app_spec)
    app_mod.__package__ = "web"
    sys.modules["web.app"] = app_mod
    app_spec.loader.exec_module(app_mod)

    return app_mod


# =====================================================================
# SECTION 1 — P0 Regressions: Dead-Code Removal (flow.py, chatbot.py)
# =====================================================================


class TestP0_EvenHistoryProcessing:
    """P0 Fix #3: Unreachable guard `if history_length % 2 != 0` removed.

    Bug mode if reverted: Guard was always False (turn index × 2 = always even),
    so dead code executed on every turn. Its removal has no functional effect
    but the regression test validates that even-turn histories process without error.
    """

    def test_even_history_advance_does_not_raise(self):
        """Engine with even-entry history (normal state) must advance cleanly."""
        engine = SalesFlowEngine("consultative", "products")
        engine.add_turn("hi there", "Hello!")  # 2 entries
        engine.add_turn("I need a car", "Tell me about it")  # 4 entries
        assert len(engine.conversation_history) % 2 == 0
        # Must not raise
        engine.advance()
        assert engine.current_stage == "logical"

    def test_single_turn_history_advance_does_not_raise(self):
        """One turn (2 entries) must advance without error."""
        engine = SalesFlowEngine("transactional", "fragrances")
        engine.add_turn("show me options", "Here are the options")
        engine.advance()
        assert engine.current_stage in ["intent", "pitch"]


# =====================================================================
# SECTION 2 — P1 Regressions: Deduplication Fixes
# =====================================================================


_CRITICAL_P1_RULES = [
    "Never close on a question mark",  # ban on ending pitch/close with "?"
    "Would you like",  # permission phrase ban
    "Don't ask yes/no questions",  # momentum killer ban
]


class TestP1_SharedRulesInAllStrategies:
    """P1 Fix #4: Universal P1 rules extracted to SHARED_RULES, appended to
    all get_base_rules() outputs.

    Bug mode if reverted: Rules like "NO Would you like...?# would only appear
    in one strategy branch; the other strategy could produce permission questions.

    What must hold: SHARED_RULES content appears verbatim in get_base_rules()
    output for every strategy.
    """

    @pytest.mark.parametrize("strategy", ["consultative", "transactional", "intent"])
    def test_shared_rules_present_in_all_strategies(self, strategy):
        """Every strategy's base rules must include the hard rules block."""
        rules = get_base_rules(strategy)
        assert "Hard rules" in rules, (
            f"Hard rules block missing from {strategy} strategy"
        )

    @pytest.mark.parametrize(
        "strategy,rule_fragment",
        [(s, r) for s in ["consultative", "transactional"] for r in _CRITICAL_P1_RULES],
    )
    def test_specific_p1_rule_in_strategy(self, strategy, rule_fragment):
        """Each critical P1 rule string must appear in every non-discovery strategy."""
        rules = get_base_rules(strategy)
        assert rule_fragment in rules, (
            f"P1 rule fragment '{rule_fragment}' missing from '{strategy}' strategy. "
            "This would allow permission questions or closed yes/no questions."
        )

    def test_shared_rules_not_duplicated_in_consultative(self):
        """SHARED_RULES content should appear ONCE in consultative output (not duplicated)."""
        rules = get_base_rules("consultative")
        count = rules.count("Hard rules")
        assert count == 1, (
            f"SHARED_RULES block duplicated {count} times in consultative output"
        )

    def test_shared_rules_not_duplicated_in_transactional(self):
        rules = get_base_rules("transactional")
        count = rules.count("Hard rules")
        assert count == 1, (
            f"SHARED_RULES block duplicated {count} times in transactional output"
        )


class TestP1_CommonTransitionsShared:
    """P1 Fix #7: Pitch/objection transitions extracted to COMMON_TRANSITIONS.

    Bug mode if reverted: Both strategies would define their own pitch/objection
    configs — any fix to one would need to be mirrored manually.

    What must hold: Both strategy FLOWS configs share identical pitch/objection
    transitions, and COMMON_TRANSITIONS is the source of both.
    """

    def test_common_transitions_defines_pitch_and_objection(self):
        """COMMON_TRANSITIONS must define exactly pitch and objection."""
        assert "pitch" in COMMON_TRANSITIONS
        assert "objection" in COMMON_TRANSITIONS

    def test_consultative_pitch_matches_common(self):
        c_pitch = FLOWS["consultative"]["transitions"]["pitch"]
        assert c_pitch == COMMON_TRANSITIONS["pitch"]

    def test_transactional_pitch_matches_common(self):
        t_pitch = FLOWS["transactional"]["transitions"]["pitch"]
        assert t_pitch == COMMON_TRANSITIONS["pitch"]

    def test_objection_terminal_in_both(self):
        """Both strategies: objection.next must be OUTCOME, and outcome.next must be None (terminal node)."""
        assert FLOWS["consultative"]["transitions"]["objection"]["next"] == "outcome"
        assert FLOWS["transactional"]["transitions"]["objection"]["next"] == "outcome"
        assert FLOWS["consultative"]["transitions"]["outcome"]["next"] is None
        assert FLOWS["transactional"]["transitions"]["outcome"]["next"] is None

    def test_pitch_next_is_objection_in_both(self):
        assert FLOWS["consultative"]["transitions"]["pitch"]["next"] == "objection"
        assert FLOWS["transactional"]["transitions"]["pitch"]["next"] == "objection"


class TestP1_CheckAdvancementConditionHelper:
    """P1 Fix #8: _check_advancement_condition() extracted as shared helper.

    Bug mode if reverted: _user_shows_doubt and _user_expressed_stakes would each
    contain separate copies of the same logic — a fix in one would miss the other.

    What must hold: The helper is directly callable (not only via wrappers),
    and both wrappers produce consistent results.
    """

    def test_helper_callable_directly(self):
        """_check_advancement_condition must be importable and callable."""
        result = _check_advancement_condition([], "struggling at work", 3, "logical")
        assert isinstance(result, bool)

    def test_helper_respects_min_turns(self):
        """Even with doubt signal, helper must not advance before min_turns."""
        history = [{"role": "user", "content": "it's not working for me"}]
        result = _check_advancement_condition(
            history, "struggling badly", 0, "logical", min_turns=2
        )
        # Turn 0 < min_turns(2) — should NOT advance
        assert result is False

    def test_doubt_wrapper_uses_logical_stage(self):
        """_user_shows_doubt delegates to helper with 'logical' stage (min_turns=2)."""
        # No advancement at turn 0 even with doubt keyword
        history = [{"role": "user", "content": "it's not working"}]
        assert _user_shows_doubt(history, "not working for me", 0) is False

    def test_stakes_wrapper_uses_emotional_stage(self):
        """_user_expressed_stakes delegates to helper with 'emotional' stage (min_turns=3)."""
        history = [{"role": "user", "content": "it's costing me clients"}]
        assert _user_expressed_stakes(history, "really losing money", 1) is False

    def test_wrappers_consistent_with_helper_on_advancement(self):
        """Verify wrappers return same value as calling helper directly."""
        history = [
            {"role": "user", "content": "it's not working at all"},
            {"role": "assistant", "content": "I see"},
            {"role": "user", "content": "been struggling constantly"},
        ]
        helper_result = _check_advancement_condition(
            history, "nothing helps", 3, "logical", min_turns=2
        )
        wrapper_result = _user_shows_doubt(history, "nothing helps", 3)
        assert helper_result == wrapper_result


# =====================================================================
# SECTION 3 — P2 Regressions: Bug Fixes
# =====================================================================


_SHOULD_NOT_TRIGGER_HIGH_INTENT = [
    "i want to make more money",  # "want to" alone (removed)
    "i need to think about it",  # "need to" alone (removed)
    "trying a new recipe later",  # "trying" alone with no sales context (removed)
    "looking to upgrade eventually",  # vague — "looking to" without urgency
    "i'm ready to learn more",  # "ready to" alone (removed)
]


class TestP2_GoalIndicatorsCleanup:
    """P2 Fix #10: 11 near-universal verbs removed from goal_indicators in
    analysis_config.yaml to prevent premature intent lock.

    Bug mode if reverted: Messages like "I want to make dinner" or "need more
    time" would classify as high_intent, causing the FSM to skip discovery.
    """

    @pytest.mark.parametrize("phrase", _SHOULD_NOT_TRIGGER_HIGH_INTENT)
    def test_generic_phrases_do_not_trigger_high_intent(self, phrase):
        """Phrases with removed near-universal verbs must NOT classify as high_intent."""
        result = analyse_state([], user_message=phrase)
        assert result["intent"] != "high", (
            f"'{phrase}' incorrectly triggered high_intent. Likely a removed goal_indicator verb was re-added."
        )

    def test_specific_goal_still_triggers_high_intent(self):
        """Specific buying goals that weren't removed must still work."""
        result = analyse_state([], "shopping for a new car")
        assert result["intent"] == "high"

    def test_goal_indicators_no_near_universal_verbs(self):
        """Config must not contain removed near-universal verbs as standalone entries."""
        config = load_analysis_config()
        goal_indicators = config.get("goal_indicators", [])
        # These were explicitly removed — presence means regression
        forbidden_standalone = [
            "want to",
            "need to",
            "trying",
            "fix",
            "solve",
            "improve",
            "upgrade",
            "replace",
            "better",
            "ready to",
            "time to",
        ]
        for verb in forbidden_standalone:
            assert verb not in goal_indicators, (
                f"Near-universal verb '{verb}' reappeared in goal_indicators — "
                "this causes premature intent lock on generic conversation."
            )


class TestP2_DetectAndSwitchStrategyReturnsBoolean:
    """P2 Fix #12: _detect_and_switch_strategy() extracted with SRP.

    Bug mode if reverted: Strategy detection and FSM advancement would be
    entangled — you could not test them independently.

    What must hold: Method is callable, returns bool, doesn't mutate state
    when no transactional signal is present.
    """

    def test_returns_bool_on_no_signal(self):
        bot = SalesChatbot(product_type="general")
        result = bot._detect_and_switch_strategy("hello how are you")
        assert isinstance(result, bool)

    def test_returns_false_on_neutral_message(self):
        bot = SalesChatbot(product_type="general")
        result = bot._detect_and_switch_strategy("I'm not sure what I'm looking for")
        assert result is False

    def test_does_not_change_flow_type_on_false_return(self):
        """When False returned, flow type must remain unchanged."""
        bot = SalesChatbot(product_type="general")
        original_type = bot.flow_engine.flow_type
        bot._detect_and_switch_strategy("hello")
        assert bot.flow_engine.flow_type == original_type

    def test_isolation_from_fsm_state(self):
        """Calling _detect_and_switch_strategy must not advance FSM stage."""
        bot = SalesChatbot(product_type="general")
        original_stage = bot.flow_engine.current_stage
        bot._detect_and_switch_strategy("just a test")
        assert bot.flow_engine.current_stage == original_stage


# =====================================================================
# SECTION 4 — P3 Regressions: Operational Fixes
# =====================================================================


class TestP3_NoMaxReframesInConfig:
    """P3 Fix #13: `max_reframes` block deleted from analysis_config.yaml.

    Bug mode if reverted: A dead config key would re-appear, misleading
    future developers into thinking there's a reframe-count limit in effect.

    What must hold: `max_reframes` key does NOT exist in the loaded config.
    """

    def test_max_reframes_not_inANALYSIS_CONFIG(self):
        """analysis_config.yaml must NOT contain the deleted max_reframes key."""
        config = load_analysis_config()
        assert "max_reframes" not in config, (
            "Deleted key 'max_reframes' reappeared in analysis_config.yaml. "
            "This is a dead config block with no code reading it."
        )


class TestP3_MetricsRotationConstant:
    """P3 Fix #14: MAX_METRICS_LINES rotation cap added to performance.py.

    Bug mode if reverted: The metrics.jsonl file would grow unboundedly,
    eventually filling disk on long-running deployments.

    What must hold: MAX_METRICS_LINES constant exists and is 5000.
    Rotation trimming must fire when file exceeds the cap.
    """

    def test_rotation_constant_exists_and_is_correct(self):
        """MAX_METRICS_LINES must be importable and equal 5000."""
        assert MAX_METRICS_LINES == 5000, (
            f"MAX_METRICS_LINES changed from 5000 to {MAX_METRICS_LINES}. "
            "Restore to 5000 or update the rotation logic accordingly."
        )

    def test_file_trimmed_when_over_cap(self):
        """Writing more than MAX_METRICS_LINES lines must trigger rotation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for i in range(MAX_METRICS_LINES):
                f.write(json.dumps({"seq": i}) + "\n")
            temp_path = f.name

        try:
            from chatbot.analytics import performance
            from chatbot.analytics.jsonl_store import JSONLWriter

            temp_writer = JSONLWriter(
                temp_path, MAX_METRICS_LINES, MAX_METRICS_LINES // 2
            )
            original_get = performance.get_writer
            performance.get_writer = lambda: temp_writer

            PerformanceTracker.log_stage_latency(
                session_id="rotation_test",
                stage="intent",
                strategy="consultative",
                latency_ms=100.0,
                provider="groq",
                model="test",
                user_message_length=5,
                bot_response_length=10,
            )

            with open(temp_path) as f:
                lines = f.readlines()

            assert len(lines) <= MAX_METRICS_LINES // 2 + 10, (
                f"Rotation did not trim the file: {len(lines)} lines remain after rotation"
            )
        finally:
            performance.get_writer = original_get
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class TestP3_DebugPanelGated:
    """P3 Fix #15: _DEBUG_ENABLED gate added — /api/debug/* returns 403
    unless ENABLE_DEBUG_PANEL=true env var is set.

    Bug mode if reverted: Debug endpoints would be publicly accessible,
    exposing session internals to unauthenticated users.

    What must hold: With default env (no ENABLE_DEBUG_PANEL), all debug
    routes return 403 Forbidden.
    """

    @pytest.fixture(autouse=True)
    def flask_client(self):
        os.environ.pop("ENABLE_DEBUG_PANEL", None)
        app_mod = _load_web_app()
        # Force _DEBUG_ENABLED to False to handle module caching across test runs
        app_mod._DEBUG_ENABLED = False
        app_mod.app.config["TESTING"] = True
        self.client = app_mod.app.test_client()

    def test_debug_endpoint_blocked_by_default(self):
        """/api/debug/ must return 403 when ENABLE_DEBUG_PANEL is unset."""
        resp = self.client.get("/api/debug/sessions")
        assert resp.status_code == 403, (
            f"Debug panel returned {resp.status_code} instead of 403. "
            "Debug endpoints are publicly accessible — security regression."
        )

    def test_debug_subpath_blocked(self):
        resp = self.client.get("/api/debug/anything")
        assert resp.status_code == 403

    def test_non_debug_endpoint_not_blocked(self):
        """Health endpoint must NOT be blocked by the debug gate."""
        resp = self.client.get("/api/health")
        assert resp.status_code == 200

    # Additional tests continue below in the original file (unchanged)


# =====================================================================
# SECTION 1 — P0 Regressions: Dead-Code Removal (flow.py, chatbot.py)
# =====================================================================


class TestP0_FlowsHaveNoMaxTurns:
    """P0 Fix #2: `max_turns` YAML keys removed from FLOWS intent stages.

    Bug mode if reverted: FLOWS["consultative"]["transitions"]["intent"] would
    contain a `max_turns` key that no code reads, creating false documentation
    and a misleading config surface for future developers.

    What must hold: No intent-stage transition config in any strategy
    should contain a `max_turns` key.
    """

    @pytest.mark.parametrize("strategy", ["consultative", "transactional"])
    def test_intent_stage_has_no_max_turns_key(self, strategy):
        """Intent transition config must NOT have max_turns (never read by FSM)."""
        intent_config = FLOWS[strategy]["transitions"]["intent"]
        assert "max_turns" not in intent_config, (
            f"FLOWS['{strategy}']['transitions']['intent'] still has 'max_turns' — "
            "dead key from pre-fix config. Remove it."
        )

    def test_intent_only_flow_has_no_max_turns(self):
        """The 'intent' discovery-only flow also must not carry max_turns."""
        intent_config = FLOWS["intent"]["transitions"]["intent"]
        assert "max_turns" not in intent_config
