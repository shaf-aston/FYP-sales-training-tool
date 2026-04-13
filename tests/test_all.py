"""Test suite for sales chatbot — signals, preferences, config, knowledge, and aliases.

Covers the Verification stage of the software lifecycle (CS3IP Section 1.2).
Tests here cover modules NOT already tested in dedicated files.

Dedicated test files handle:
- FSM flow/advancement: test_regression_and_security.py
- Objection classification: test_objection_sop.py
- Intent lock / literal questions / frustration: test_priority_fixes.py
- Acknowledgment tactics: test_acknowledgment_tactics.py
- Provider architecture: test_regression_and_security.py
- Web endpoints / security: test_regression_and_security.py
"""

import pytest

from chatbot.analysis import (
    extract_preferences,
    extract_user_keywords,
    user_demands_directness,
)
from chatbot.chatbot import SalesChatbot
from chatbot.content import SIGNALS
from chatbot.knowledge import (
    KNOWLEDGE_FILE,
    clear_custom_knowledge,
    get_custom_knowledge_text,
    load_custom_knowledge,
    save_custom_knowledge,
)
from chatbot.loader import get_product_settings, load_product_config, loadSIGNALS
from chatbot.providers.base import BaseLLMProvider, LLMResponse
from chatbot.providers.factory import PROVIDERS, create_provider
from chatbot.providers.groq_provider import GroqProvider
from chatbot.utils import contains_nonnegated_keyword

# ====================================================================
# SECTION 1 — Keyword & Signal Utilities (analysis.py)
# ====================================================================


class TestKeywordMatching:
    """Word-boundary keyword detection — the foundation of signal analysis."""

    def test_case_insensitive_match(self):
        """Impatience signals should match regardless of case."""
        assert contains_nonnegated_keyword("JUST SHOW ME something", SIGNALS["impatience"])

    def test_word_boundary_no_false_positive(self):
        """'just' must NOT match inside 'justice' (word boundary regex)."""
        assert not contains_nonnegated_keyword("justice is served", ["just"])

    def test_empty_text_returns_false(self):
        assert not contains_nonnegated_keyword("", SIGNALS["impatience"])

    def test_none_text_returns_false(self):
        assert not contains_nonnegated_keyword(None, SIGNALS["impatience"])

    def test_commitment_signal(self):
        assert contains_nonnegated_keyword("yes let's do it", SIGNALS["commitment"])

    def test_no_match_on_unrelated_text(self):
        assert not contains_nonnegated_keyword("the weather is nice today", SIGNALS["impatience"])


class TestSignalsConfig:
    """Verify the SIGNALS dictionary loaded from signals.yaml."""

    def test_expected_categories_exist(self):
        required = [
            "impatience",
            "commitment",
            "objection",
            "walking",
            "low_intent",
            "high_intent",
            "guardedness_keywords",
            "direct_info_requests",
        ]
        for cat in required:
            assert cat in SIGNALS, f"Missing signal category: {cat}"

    def test_categories_are_non_empty(self):
        for cat in ["impatience", "commitment", "objection"]:
            assert len(SIGNALS[cat]) >= 5, f"{cat} should have at least 5 keywords"


# ====================================================================
# SECTION 2 — Preference & Directness Detection (analysis.py)
# ====================================================================


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

    def test_filtersSTOP_WORDS(self):
        history = [{"role": "user", "content": "I want to get a car"}]
        keywords = extract_user_keywords(history)
        assert "want" not in keywords  # stop word
        assert "car" in keywords


# ====================================================================
# SECTION 3 — Chatbot Init & Rewind (chatbot.py)
# ====================================================================


class TestChatbotInit:
    """SalesChatbot initialisation via product config."""

    def test_default_is_intent_discovery(self):
        bot = SalesChatbot(product_type="general")
        assert bot.flow_engine.flow_type == "intent"
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
# SECTION 4 — Config Loading (config_loader.py)
# ====================================================================


class TestConfigLoading:
    """YAML config files load correctly and contain expected data."""

    def testSIGNALS_returns_dict(self):
        signals = loadSIGNALS()
        assert isinstance(signals, dict)
        assert "impatience" in signals

    def test_product_config_has_products(self):
        config = load_product_config()
        assert "products" in config
        assert "default" in config["products"]

    def test_product_settings_returns_strategy_and_context(self):
        settings = get_product_settings("general")
        assert "strategy" in settings
        assert "context" in settings
        assert settings["strategy"] in ["consultative", "transactional", "intent"]

    def test_unknown_product_falls_back_to_default(self):
        settings = get_product_settings("nonexistent_product_xyz")
        assert "strategy" in settings


# ====================================================================
# SECTION 5 — Product Knowledge Config (config_loader.py)
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

    def test_default_product_has_knowledge(self):
        """Default product includes knowledge in context."""
        bot = SalesChatbot(product_type="general")
        assert "PRODUCT KNOWLEDGE" in bot.flow_engine.product_context


# ====================================================================
# SECTION 6 — Knowledge Base (knowledge.py)
# ====================================================================


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
# SECTION 7 — Product Alias Resolution (config_loader.py)
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
# SECTION 8 — Provider Architecture (providers/)
# ====================================================================


class TestProviderBase:
    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseLLMProvider()

    def test_llm_response_fields(self):
        resp = LLMResponse(content="hello", model="test", latency_ms=42.5)
        assert resp.content == "hello"
        assert resp.latency_ms == 42.5
        assert resp.error is None

    def test_llm_response_with_error(self):
        resp = LLMResponse(content="", model="test", latency_ms=0, error="timeout")
        assert resp.error == "timeout"


class TestProviderFactory:
    def test_create_groq(self):
        assert isinstance(create_provider("groq"), GroqProvider)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("openai")

    def test_case_insensitive(self):
        assert isinstance(create_provider("GROQ"), GroqProvider)

    def test_registry_has_groq(self):
        assert "groq" in PROVIDERS
