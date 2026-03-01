"""Test suite for sales chatbot — FSM, analysis, advancement rules, and config.

Covers the Verification stage of the software lifecycle (CS3IP Section 1.2).
Tests are grouped by module and test behaviour, not just initial state.
"""

import sys, os, pytest

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chatbot.analysis import (
    text_contains_any_keyword,
    analyze_state,
    extract_preferences,
    extract_recent_user_messages,
    user_demands_directness,
    is_literal_question,
    extract_user_keywords,
    classify_objection,
    _has_user_stated_clear_goal,
)
from chatbot.content import SIGNALS
from chatbot.flow import (
    SalesFlowEngine,
    FLOWS,
    user_has_clear_intent,
    user_shows_doubt,
    commitment_or_objection,
    commitment_or_walkaway,
)
from chatbot.config_loader import load_signals, load_product_config, get_product_settings


# Set a dummy key so SalesChatbot can be instantiated without a real provider
os.environ.setdefault("GROQ_API_KEY", "test_key")

from chatbot.chatbot import SalesChatbot


# ====================================================================
# SECTION 1 — Keyword & Signal Utilities (analysis.py)
# ====================================================================

class TestKeywordMatching:
    """Word-boundary keyword detection — the foundation of signal analysis."""

    def test_case_insensitive_match(self):
        """Impatience signals should match regardless of case."""
        assert text_contains_any_keyword("JUST SHOW ME something", SIGNALS["impatience"])

    def test_word_boundary_no_false_positive(self):
        """'just' must NOT match inside 'justice' (word boundary regex)."""
        assert not text_contains_any_keyword("justice is served", ["just"])

    def test_empty_text_returns_false(self):
        assert not text_contains_any_keyword("", SIGNALS["impatience"])

    def test_none_text_returns_false(self):
        assert not text_contains_any_keyword(None, SIGNALS["impatience"])

    def test_commitment_signal(self):
        assert text_contains_any_keyword("yes let's do it", SIGNALS["commitment"])

    def test_no_match_on_unrelated_text(self):
        assert not text_contains_any_keyword("the weather is nice today", SIGNALS["impatience"])


class TestSignalsConfig:
    """Verify the SIGNALS dictionary loaded from signals.yaml."""

    def test_expected_categories_exist(self):
        required = ["impatience", "commitment", "objection", "walking",
                     "low_intent", "high_intent", "guarded", "direct_info_requests"]
        for cat in required:
            assert cat in SIGNALS, f"Missing signal category: {cat}"

    def test_categories_are_non_empty(self):
        for cat in ["impatience", "commitment", "objection"]:
            assert len(SIGNALS[cat]) >= 5, f"{cat} should have at least 5 keywords"


# ====================================================================
# SECTION 2 — State Analysis (analysis.py)
# ====================================================================

class TestAnalyzeState:
    """Intent, guardedness, and question-fatigue detection."""

    def test_high_intent_keyword(self):
        result = analyze_state([], user_message="I need help with my car")
        assert result["intent"] == "high"

    def test_low_intent_keyword(self):
        result = analyze_state([], user_message="just browsing really")
        assert result["intent"] == "low"

    def test_medium_intent_default(self):
        result = analyze_state([], user_message="hello there")
        assert result["intent"] == "medium"

    def test_guarded_short_defensive(self):
        """Short + guarded keyword after a bot question → guarded=True."""
        history = [{"role": "assistant", "content": "What brings you in today?"}]
        result = analyze_state(history, user_message="idk")
        assert result["guarded"] is True

    def test_not_guarded_on_substantive_reply(self):
        """If user previously gave a long answer then says 'ok', that's agreement not guardedness."""
        history = [
            {"role": "user", "content": "I have been looking for something reliable and safe for my family to drive every day"},
            {"role": "assistant", "content": "That makes sense, safety is important?"},
        ]
        result = analyze_state(history, user_message="ok")
        assert result["guarded"] is False

    def test_question_fatigue(self):
        """2+ consecutive bot questions should trigger question fatigue."""
        history = [
            {"role": "assistant", "content": "What are you looking for?"},
            {"role": "user", "content": "a car"},
            {"role": "assistant", "content": "What's your budget?"},
            {"role": "user", "content": "not sure"},
        ]
        result = analyze_state(history, user_message="ugh")
        assert result["question_fatigue"] is True


class TestPreferenceExtraction:
    """extract_preferences should find mentioned preference categories."""

    def test_budget_and_safety_detected(self):
        history = [
            {"role": "user", "content": "I need something affordable and safe for my kids"},
            {"role": "assistant", "content": "ok"},
        ]
        prefs = extract_preferences(history)
        assert "budget" in prefs
        assert "safety" in prefs

    def test_empty_history_returns_empty(self):
        assert extract_preferences([]) == ""

    def test_no_preferences_in_greeting(self):
        history = [{"role": "user", "content": "hi there"}]
        assert extract_preferences(history) == ""


class TestDirectnessDetection:
    """user_demands_directness should fire on frustration signals."""

    def test_demand_directness(self):
        assert user_demands_directness([], "just tell me the price already")

    def test_repeated_frustration(self):
        history = [
            {"role": "user", "content": "what's the price"},
            {"role": "assistant", "content": "Let me understand your needs first"},
        ]
        assert user_demands_directness(history, "i said what's the price")

    def test_no_false_positive_on_greeting(self):
        assert not user_demands_directness([], "hello, how are you")


class TestUserKeywords:
    """extract_user_keywords for lexical entrainment."""

    def test_extracts_meaningful_words(self):
        history = [{"role": "user", "content": "I'm looking for a reliable sedan"}]
        keywords = extract_user_keywords(history)
        assert "reliable" in keywords
        assert "sedan" in keywords

    def test_filters_stop_words(self):
        history = [{"role": "user", "content": "I want to get a car"}]
        keywords = extract_user_keywords(history)
        assert "want" not in keywords  # stop word
        assert "car" in keywords


# ====================================================================
# SECTION 3 — FSM Flow Engine (flow.py)
# ====================================================================

class TestFlowInit:
    """SalesFlowEngine initialisation and configuration."""

    def test_consultative_has_five_stages(self):
        engine = SalesFlowEngine("consultative", "luxury vehicles")
        assert engine.flow_config["stages"] == ["intent", "logical", "emotional", "pitch", "objection"]
        assert engine.current_stage == "intent"

    def test_transactional_has_three_stages(self):
        engine = SalesFlowEngine("transactional", "$30 fragrances")
        assert engine.flow_config["stages"] == ["intent", "pitch", "objection"]
        assert engine.current_stage == "intent"

    def test_invalid_flow_raises(self):
        with pytest.raises(ValueError):
            SalesFlowEngine("unknown_flow", "context")


class TestFlowStateManagement:
    """Turn tracking, advancement, and terminal state."""

    def test_add_turn_updates_history_and_counter(self):
        engine = SalesFlowEngine("consultative", "products")
        engine.add_turn("hi", "Hello! How can I help?")
        assert len(engine.conversation_history) == 2
        assert engine.stage_turn_count == 1

    def test_sequential_advance_full_consultative(self):
        """Advance through all 5 consultative stages in order."""
        engine = SalesFlowEngine("consultative", "products")
        expected = ["logical", "emotional", "pitch", "objection"]
        for stage in expected:
            engine.advance()
            assert engine.current_stage == stage

    def test_direct_jump_to_pitch(self):
        engine = SalesFlowEngine("consultative", "products")
        engine.advance(target_stage="pitch")
        assert engine.current_stage == "pitch"

    def test_advance_at_terminal_stays(self):
        """Advancing at the last stage (objection) should not crash or change stage."""
        engine = SalesFlowEngine("transactional", "products")
        # Move to objection (terminal)
        engine.advance()  # intent → pitch
        engine.advance()  # pitch → objection
        assert engine.current_stage == "objection"
        engine.advance()  # should stay
        assert engine.current_stage == "objection"

    def test_advance_resets_turn_count(self):
        engine = SalesFlowEngine("consultative", "products")
        engine.add_turn("hi", "hey")
        engine.add_turn("hello", "hi there")
        assert engine.stage_turn_count == 2
        engine.advance()
        assert engine.stage_turn_count == 0

    def test_get_summary(self):
        engine = SalesFlowEngine("consultative", "products")
        engine.add_turn("hi", "hello")
        summary = engine.get_summary()
        assert summary["flow_type"] == "consultative"
        assert summary["current_stage"] == "intent"
        assert summary["total_turns"] == 1


# ====================================================================
# SECTION 4 — Advancement Rules (flow.py)
# ====================================================================

class TestAdvancementRules:
    """Pure-function advancement rules that drive FSM transitions."""

    def test_intent_advance_on_buy(self):
        assert user_has_clear_intent([], "I want to buy a car", 0)

    def test_intent_advance_on_need(self):
        assert user_has_clear_intent([], "I need help with something", 0)

    def test_intent_no_advance_on_greeting(self):
        assert not user_has_clear_intent([], "hello there", 0)

    def test_intent_advance_on_max_turns(self):
        """Even without keywords, intent advances after max turns."""
        assert user_has_clear_intent([], "still thinking", 6)

    def test_doubt_advance_on_keyword(self):
        """Doubt keywords in history (not current msg) trigger advancement."""
        history = [
            {"role": "user", "content": "it's not working for me"}, {"role": "assistant", "content": "I see"},
            {"role": "user", "content": "yeah I'm struggling"}, {"role": "assistant", "content": "ok"},
        ]
        assert user_shows_doubt(history, "what should I do", 3)

    def test_commitment_advances_pitch(self):
        assert commitment_or_objection([], "yes let's do it", 0)

    def test_objection_advances_pitch(self):
        assert commitment_or_objection([], "but that seems too much", 0)

    def test_neutral_does_not_advance_pitch(self):
        assert not commitment_or_objection([], "tell me more about it", 0)

    def test_walkaway_ends_objection(self):
        assert commitment_or_walkaway([], "no thanks, not interested", 0)

    def test_commitment_ends_objection(self):
        assert commitment_or_walkaway([], "yes I'm in", 0)


class TestShouldAdvance:
    """Integration: should_advance on the engine (frustration, urgency, rules)."""

    def test_impatience_skips_to_pitch(self):
        engine = SalesFlowEngine("consultative", "products")
        engine.advance()  # intent → logical (has urgency_skip_to)
        result = engine.should_advance("just show me the options already")
        assert result == "pitch"

    def test_frustration_override_jumps_to_pitch(self):
        engine = SalesFlowEngine("consultative", "products")
        result = engine.should_advance("just tell me the price, stop wasting my time")
        assert result == "pitch"

    def test_no_advance_on_neutral(self):
        engine = SalesFlowEngine("consultative", "products")
        result = engine.should_advance("hello")
        assert result is False


# ====================================================================
# SECTION 5 — Chatbot Integration (chatbot.py)
# ====================================================================

class TestChatbotInit:
    """SalesChatbot initialisation via product config."""

    def test_default_is_consultative(self):
        bot = SalesChatbot(product_type="general")
        assert bot.flow_engine.flow_type == "consultative"
        assert bot.flow_engine.current_stage == "intent"

    def test_transactional_product(self):
        bot = SalesChatbot(product_type="budget_fragrances")
        assert bot.flow_engine.flow_type == "transactional"
        assert bot.flow_engine.flow_config["stages"] == ["intent", "pitch", "objection"]


class TestChatbotRewind:
    """rewind_to_turn must hard-reset and replay."""

    def test_rewind_to_zero_resets(self):
        bot = SalesChatbot(product_type="general")
        bot.flow_engine.add_turn("hi", "hello")
        bot.flow_engine.add_turn("help", "sure")
        assert bot.rewind_to_turn(0) is True
        assert len(bot.flow_engine.conversation_history) == 0
        assert bot.flow_engine.current_stage == "intent"
        assert bot.flow_engine.stage_turn_count == 0

    def test_rewind_to_one_keeps_first_turn(self):
        bot = SalesChatbot(product_type="general")
        bot.flow_engine.add_turn("hi", "hello")
        bot.flow_engine.add_turn("help", "sure")
        assert bot.rewind_to_turn(1) is True
        assert len(bot.flow_engine.conversation_history) == 2

    def test_rewind_invalid_index(self):
        bot = SalesChatbot(product_type="general")
        assert bot.rewind_to_turn(5) is False

    def test_history_truncation_for_edits(self):
        """Manual history truncation works (used by edit feature)."""
        bot = SalesChatbot(product_type="general")
        bot.flow_engine.conversation_history = [
            {"role": "user", "content": "Test 1"},
            {"role": "assistant", "content": "Response 1"},
            {"role": "user", "content": "Test 2"},
            {"role": "assistant", "content": "Response 2"},
        ]
        bot.flow_engine.conversation_history = bot.flow_engine.conversation_history[:2]
        assert len(bot.flow_engine.conversation_history) == 2
        assert bot.flow_engine.conversation_history[0]["content"] == "Test 1"


# ====================================================================
# SECTION 6 — Config Loading (config_loader.py)
# ====================================================================

class TestConfigLoading:
    """YAML config files load correctly and contain expected data."""

    def test_signals_returns_dict(self):
        signals = load_signals()
        assert isinstance(signals, dict)
        assert "impatience" in signals

    def test_product_config_has_products(self):
        config = load_product_config()
        assert "products" in config
        assert "general" in config["products"]

    def test_product_settings_returns_strategy_and_context(self):
        settings = get_product_settings("general")
        assert "strategy" in settings
        assert "context" in settings
        assert settings["strategy"] in ["consultative", "transactional"]

    def test_unknown_product_falls_back_to_default(self):
        settings = get_product_settings("nonexistent_product_xyz")
        assert "strategy" in settings


# ====================================================================
# SECTION 7 — Literal Question Detection (analysis.py)
# ====================================================================

class TestLiteralQuestion:
    """is_literal_question — Speech Act Theory classification."""

    def test_question_word_detected(self):
        assert is_literal_question("What options do you have?")

    def test_question_mark_detected(self):
        assert is_literal_question("Is this available?")

    def test_rhetorical_excluded(self):
        assert not is_literal_question("That's great, don't you think?")

    def test_statement_not_question(self):
        assert not is_literal_question("I want something reliable")

    def test_empty_returns_false(self):
        assert not is_literal_question("")


# ====================================================================
# SECTION 8 — Objection Classification (analysis.py)
# ====================================================================

class TestObjectionClassification:
    """classify_objection — maps objections to reframe strategies."""

    def test_money_objection_detected(self):
        result = classify_objection("that's too expensive for me")
        assert result["type"] == "money"
        assert result["strategy"] in ["isolate_funds", "self_solve", "plant_credit", "funding_options"]

    def test_partner_objection_detected(self):
        result = classify_objection("I need to check with my wife first")
        assert result["type"] == "partner"
        assert result["strategy"] in ["same_side", "open_wallet_test", "schedule_followup"]

    def test_fear_objection_detected(self):
        result = classify_objection("I'm worried this might not work for me")
        assert result["type"] == "fear"
        assert result["strategy"] in ["change_of_process", "island_analogy", "identity_reframe"]

    def test_logistical_objection_detected(self):
        result = classify_objection("the setup process seems too complicated")
        assert result["type"] == "logistical"
        assert result["strategy"] in ["solve_mechanics", "simplify_process"]

    def test_think_objection_detected(self):
        result = classify_objection("let me think about it")
        assert result["type"] == "think"
        assert result["strategy"] in ["drill_to_root", "handle_root_type"]

    def test_smokescreen_detected(self):
        result = classify_objection("no thanks, not for me")
        assert result["type"] == "smokescreen"
        assert result["strategy"] == "legitimacy_test"

    def test_unknown_objection_returns_general(self):
        result = classify_objection("hmm I see")
        assert result["type"] == "unknown"
        assert result["strategy"] == "general_reframe"

    def test_guidance_is_non_empty(self):
        """Every classification should return actionable guidance."""
        result = classify_objection("that's too expensive")
        assert len(result["guidance"]) > 10

    def test_classification_uses_history_context(self):
        """Objection classification should check recent history, not just current message."""
        history = [
            {"role": "user", "content": "how much does it cost?"},
            {"role": "assistant", "content": "The investment is $5,000"},
        ]
        result = classify_objection("hmm that's a lot", history)
        assert result["type"] == "money"  # "cost" in history + "a lot" signals money


# ====================================================================
# SECTION 9 — Intent Lock & Goal Priming (analysis.py)
# ====================================================================

class TestIntentLock:
    """Intent Lock with Goal Priming (Chartrand & Bargh, 1996)."""

    def test_goal_priming_detects_explicit_goals(self):
        history = [
            {"role": "user", "content": "I want to lose weight"},
            {"role": "assistant", "content": "Great! How much weight?"},
        ]
        assert _has_user_stated_clear_goal(history) is True

    def test_goal_priming_empty_history(self):
        assert _has_user_stated_clear_goal([]) is False

    def test_intent_lock_prevents_reversion(self):
        """Turn 14-16 scenario: goal stated, then short 'idk' — intent stays HIGH."""
        history = [
            {"role": "user", "content": "I want to lose weight"},
            {"role": "assistant", "content": "How much weight do you want to lose?"},
        ]
        state = analyze_state(history, "idk")
        assert state["intent"] == "high"

    def test_agreement_pattern_not_guarded(self):
        """Turn 28 scenario: 'ok' after substantive answer = agreement, not guarded."""
        history = [
            {"role": "assistant", "content": "What's your primary fitness goal?"},
            {"role": "user", "content": "I want to lose about twenty pounds this year"},
            {"role": "assistant", "content": "That sounds achievable. Here are some options."},
        ]
        state = analyze_state(history, "ok")
        assert state["guarded"] is False


# ====================================================================
# SECTION 10 — Product Knowledge Config (config_loader.py)
# ====================================================================

class TestProductKnowledge:
    """Product config with enriched knowledge field."""

    def test_car_product_has_knowledge(self):
        settings = get_product_settings("car")
        assert "knowledge" in settings
        assert "Toyota Corolla" in settings["knowledge"]

    def test_luxury_cars_has_knowledge(self):
        settings = get_product_settings("luxury_cars")
        assert "knowledge" in settings
        assert "BMW" in settings["knowledge"]

    def test_product_knowledge_injected_in_context(self):
        """SalesChatbot should include product knowledge in flow engine context."""
        bot = SalesChatbot(product_type="car")
        assert "PRODUCT KNOWLEDGE" in bot.flow_engine.product_context

    def test_general_product_has_no_knowledge(self):
        """Products without knowledge field should still work."""
        bot = SalesChatbot(product_type="general")
        assert "PRODUCT KNOWLEDGE" not in bot.flow_engine.product_context


# ====================================================================
# SECTION 11 — Provider Architecture (providers/)
# ====================================================================

from chatbot.providers.base import BaseLLMProvider, LLMResponse
from chatbot.providers.factory import create_provider, PROVIDERS
from chatbot.providers.ollama_provider import OllamaProvider
from chatbot.providers.groq_provider import GroqProvider


class TestProviderBase:
    """Abstract base class and LLMResponse dataclass."""

    def test_abc_cannot_instantiate(self):
        """BaseLLMProvider is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError):
            BaseLLMProvider()

    def test_llm_response_fields(self):
        """LLMResponse dataclass stores content, model, latency, optional error."""
        resp = LLMResponse(content="hello", model="test", latency_ms=42.5)
        assert resp.content == "hello"
        assert resp.model == "test"
        assert resp.latency_ms == 42.5
        assert resp.error is None

    def test_llm_response_with_error(self):
        resp = LLMResponse(content="", model="test", latency_ms=0, error="timeout")
        assert resp.error == "timeout"


class TestOllamaProviderConfig:
    """OllamaProvider initialisation and configuration (no live server needed)."""

    def test_default_model(self):
        provider = OllamaProvider()
        assert provider.model == "phi3:mini"

    def test_custom_model(self):
        provider = OllamaProvider(model="llama3:8b")
        assert provider.model == "llama3:8b"

    def test_default_base_url(self):
        provider = OllamaProvider()
        assert "localhost" in provider.base_url
        assert "11434" in provider.base_url

    def test_endpoints_defined(self):
        assert OllamaProvider.CHAT_ENDPOINT == "/api/chat"
        assert OllamaProvider.TAGS_ENDPOINT == "/api/tags"

    def test_unavailable_returns_error_response(self):
        """When Ollama is not running, chat() should return LLMResponse with error."""
        provider = OllamaProvider(base_url="http://localhost:99999")
        resp = provider.chat([{"role": "user", "content": "test"}])
        assert isinstance(resp, LLMResponse)
        assert resp.error is not None
        assert resp.content == ""

    def test_availability_cache_initialised(self):
        provider = OllamaProvider()
        assert provider._available_cache is None
        assert provider._cache_ttl == 30


class TestGroqProviderConfig:
    """GroqProvider initialisation (no live API calls)."""

    def test_default_model(self):
        provider = GroqProvider()
        assert "llama" in provider.model or "versatile" in provider.model

    def test_no_api_key_means_unavailable(self):
        """Without SAFE_GROQ_API_KEY, provider should report unavailable."""
        old = os.environ.pop("SAFE_GROQ_API_KEY", None)
        try:
            provider = GroqProvider()
            provider.api_key = ""
            assert provider.is_available() is False
        finally:
            if old is not None:
                os.environ["SAFE_GROQ_API_KEY"] = old


class TestProviderFactory:
    """create_provider factory function."""

    def test_create_groq(self):
        provider = create_provider("groq")
        assert isinstance(provider, GroqProvider)

    def test_create_ollama(self):
        provider = create_provider("ollama")
        assert isinstance(provider, OllamaProvider)

    def test_unknown_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("openai")

    def test_case_insensitive(self):
        provider = create_provider("GROQ")
        assert isinstance(provider, GroqProvider)

    def test_registry_has_expected_providers(self):
        assert "groq" in PROVIDERS
        assert "ollama" in PROVIDERS


# ====================================================================
# SECTION 12 — Knowledge Base (knowledge.py)
# ====================================================================

from chatbot.knowledge import (
    load_custom_knowledge,
    save_custom_knowledge,
    get_custom_knowledge_text,
    clear_custom_knowledge,
    KNOWLEDGE_FILE,
)


class TestKnowledgeBase:
    """Custom knowledge CRUD and prompt injection."""

    @pytest.fixture(autouse=True)
    def cleanup_knowledge(self):
        """Ensure clean state before and after each test."""
        if KNOWLEDGE_FILE.exists():
            KNOWLEDGE_FILE.unlink()
        yield
        if KNOWLEDGE_FILE.exists():
            KNOWLEDGE_FILE.unlink()

    def test_load_missing_returns_empty(self):
        assert load_custom_knowledge() == {}

    def test_save_and_load_roundtrip(self):
        data = {"product_name": "Test Widget", "pricing": "$99/mo"}
        assert save_custom_knowledge(data) is True
        loaded = load_custom_knowledge()
        assert loaded["product_name"] == "Test Widget"
        assert loaded["pricing"] == "$99/mo"

    def test_get_text_empty_returns_empty_string(self):
        assert get_custom_knowledge_text() == ""

    def test_get_text_formats_content(self):
        save_custom_knowledge({"product_name": "Acme Pro", "pricing": "$50/mo"})
        text = get_custom_knowledge_text()
        assert "product_name: Acme Pro" in text
        assert "pricing: $50/mo" in text

    def test_clear_removes_file(self):
        save_custom_knowledge({"test": "data"})
        assert KNOWLEDGE_FILE.exists()
        assert clear_custom_knowledge() is True
        assert not KNOWLEDGE_FILE.exists()

    def test_clear_nonexistent_succeeds(self):
        """Clearing when no file exists should return True (idempotent)."""
        assert clear_custom_knowledge() is True

    def test_chatbot_includes_custom_knowledge(self):
        """When custom knowledge exists, chatbot should inject it into product context."""
        save_custom_knowledge({"product_name": "TestBot Product", "pricing": "$199/mo"})
        bot = SalesChatbot(product_type="general")
        assert "CUSTOM PRODUCT DATA" in bot.flow_engine.product_context
        assert "TestBot Product" in bot.flow_engine.product_context

    def test_chatbot_works_without_custom_knowledge(self):
        """When no custom knowledge exists, chatbot should work normally."""
        bot = SalesChatbot(product_type="general")
        assert "CUSTOM PRODUCT DATA" not in bot.flow_engine.product_context


# ====================================================================
# SECTION 13 — Product Alias Resolution (config_loader.py)
# ====================================================================

class TestProductAliases:
    """Alias resolution in get_product_settings()."""

    def test_canonical_key_works(self):
        settings = get_product_settings("automotive")
        assert settings["strategy"] == "transactional"
        assert "knowledge" in settings

    def test_car_alias_resolves(self):
        settings = get_product_settings("car")
        assert "knowledge" in settings
        assert "Toyota" in settings["knowledge"]

    def test_cars_alias_resolves(self):
        settings = get_product_settings("cars")
        assert "knowledge" in settings

    def test_vehicle_alias_resolves(self):
        settings = get_product_settings("vehicle")
        assert "knowledge" in settings

    def test_all_aliases_resolve_to_same_entry(self):
        """car, cars, vehicle should all return the same product config."""
        car = get_product_settings("car")
        cars = get_product_settings("cars")
        vehicle = get_product_settings("vehicle")
        assert car["knowledge"] == cars["knowledge"] == vehicle["knowledge"]

    def test_unknown_product_returns_default(self):
        settings = get_product_settings("nonexistent_xyz_product")
        assert "strategy" in settings

    def test_luxury_alias_resolves(self):
        settings = get_product_settings("luxury")
        assert settings["strategy"] == "consultative"

    def test_fragrance_alias_resolves(self):
        settings = get_product_settings("fragrance")
        assert settings["strategy"] == "transactional"

    def test_fitness_alias_resolves(self):
        settings = get_product_settings("gym")
        assert settings["strategy"] == "consultative"
        assert "knowledge" in settings


# ====================================================================
# SECTION 14 — Web Endpoints (app.py)
# ====================================================================

class TestWebEndpoints:
    """Flask route tests with test client."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Create Flask test client."""
        # Import app fresh
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'web'))
        from app import app
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_home_returns_200(self):
        resp = self.client.get('/')
        assert resp.status_code == 200

    def test_health_returns_ok(self):
        resp = self.client.get('/api/health')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True

    def test_init_creates_session(self):
        resp = self.client.post('/api/init', json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "session_id" in data
        assert data["stage"] == "intent"

    def test_chat_requires_session_header(self):
        resp = self.client.post('/api/chat', json={"message": "hello"})
        assert resp.status_code == 400

    def test_chat_rejects_empty_message(self):
        resp = self.client.post('/api/chat',
                                json={"message": ""},
                                headers={"X-Session-ID": "test123"})
        assert resp.status_code == 400

    def test_chat_rejects_long_message(self):
        resp = self.client.post('/api/chat',
                                json={"message": "x" * 1500},
                                headers={"X-Session-ID": "test123"})
        assert resp.status_code == 400

    def test_favicon_returns_204(self):
        resp = self.client.get('/favicon.ico')
        assert resp.status_code == 204

    def test_knowledge_page_returns_200(self):
        resp = self.client.get('/knowledge')
        assert resp.status_code == 200

    def test_knowledge_api_get(self):
        resp = self.client.get('/api/knowledge')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_knowledge_api_post_and_get(self):
        """Save knowledge, then retrieve it."""
        payload = {"product_name": "Test Product", "pricing": "$10/mo"}
        resp = self.client.post('/api/knowledge',
                                json=payload,
                                content_type='application/json')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

        # Verify it persisted
        resp2 = self.client.get('/api/knowledge')
        data2 = resp2.get_json()
        assert data2["data"]["product_name"] == "Test Product"

    def test_knowledge_api_delete(self):
        resp = self.client.delete('/api/knowledge')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_knowledge_api_post_empty_body(self):
        """POST with no JSON body should return 400."""
        resp = self.client.post('/api/knowledge',
                                data='',
                                content_type='application/json')
        # Flask will either return 400 from our validation or 400/415 from parsing
        assert resp.status_code in [400, 415]
