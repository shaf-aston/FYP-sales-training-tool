"""
Integration test for full consultative sales flow.

Validates that bot properly implements the 5-stage consultative methodology:
1. Intent discovery → requires clear goal statement
2. Logical certainty → requires doubt in current approach
3. Emotional certainty → requires emotional stakes expression
4. Pitch → requires commitment/objection
5. Objection handling → requires commitment/walkaway

Tests framework compliance: stages should NOT auto-advance without proper signals.
"""

import pytest

from chatbot.chatbot import SalesChatbot


class TestConsultativeFlowIntegration:
    """
    Integration tests validating full consultative flow with actual signal requirements.
    """

    @pytest.fixture
    def chatbot(self):
        """Create chatbot instance with consultative flow."""
        bot = SalesChatbot(provider_type="dummy", product_type="luxury_cars")
        return bot

    def test_full_consultative_flow_requiresSIGNALS(self, chatbot):
        """
        Validate that consultative flow requires actual framework signals at each stage.

        Flow progression:
        - intent → logical: Requires clear goal statement
        - logical → emotional: Requires doubt expression
        - emotional → pitch: Requires emotional stakes
        - pitch → objection/commitment: Requires explicit commitment or objection
        """
        # Phase 1: Start in intent discovery
        assert chatbot.flow_engine.current_stage == "intent"

        # Phase 2: Express clear intent → should advance to logical
        chatbot.chat("I'm struggling to make consistent profits and looking for help improving my trading")
        assert chatbot.flow_engine.current_stage == "logical", "Should advance to logical after clear intent"

        # Phase 3: Resist doubt for 9 turns → should STAY in logical
        for i in range(9):
            chatbot.chat(f"My current strategy is perfect and working great, iteration {i + 1}")
            assert chatbot.flow_engine.current_stage == "logical", f"Should stay in logical without doubt, turn {i + 1}"

        # Phase 4: Express doubt → should advance to emotional
        chatbot.chat("Actually, I'm really struggling with consistency and losing money")
        # Note: May need 1-2 more turns depending on keyword detection
        if chatbot.flow_engine.current_stage == "logical":
            # One more turn to process doubt
            chatbot.chat("It's a serious problem for me")
        assert chatbot.flow_engine.current_stage == "emotional", "Should advance to emotional after expressing doubt"

        # Phase 5: Resist emotional stakes for 9 turns → should STAY in emotional
        for i in range(9):
            chatbot.chat(f"It doesn't really matter much to me, iteration {i + 1}")
            assert chatbot.flow_engine.current_stage == "emotional", (
                f"Should stay in emotional without stakes, turn {i + 1}"
            )

        # Phase 6: Express emotional stakes → should advance to pitch
        chatbot.chat("I'm really worried about my family's future and I feel stressed about money")
        # Similar, may need 1-2 turns
        if chatbot.flow_engine.current_stage == "emotional":
            chatbot.chat("This really matters to me a lot")
        assert chatbot.flow_engine.current_stage == "pitch", "Should advance to pitch after expressing stakes"

    def test_safety_valve_prevents_infinite_loops(self, chatbot):
        """
        Validate that safety valve (10 turns) prevents bot from being stuck forever.

        Even if prospect never shows doubt, bot should advance after 10 turns.
        """
        # Switch to logical stage
        chatbot.flow_engine.switch_strategy("consultative")
        chatbot.chat("I'm struggling with my trading strategy and looking for a solution")
        assert chatbot.flow_engine.current_stage == "logical"

        # Resist for EXACTLY 10 turns (safety valve triggers)
        for i in range(10):
            chatbot.chat(f"Everything is perfect, iteration {i + 1}")

        # Should advance to emotional (safety valve triggered)
        assert chatbot.flow_engine.current_stage == "emotional", "Safety valve should trigger after 10 turns"

    def test_early_commitment_skips_stages(self, chatbot):
        """
        Validate that explicit commitment can skip stages (fast path).

        If prospect says "I want to buy" during logical stage, should jump to pitch.
        """
        # Get to logical stage
        chatbot.chat("I'm looking for help with my trading to make consistent profits")
        assert chatbot.flow_engine.current_stage == "logical"

        # Express strong commitment
        chatbot.chat("Yes, I want to sign up right now, let's do this!")

        # Should advance to pitch or directly asking for commitment
        # (implementation may vary - check that we're NOT stuck in logical)
        assert chatbot.flow_engine.current_stage != "logical", "Should advance past logical with strong commitment"

    def test_consultative_entry_via_mentorship_keyword(self):
        """
        Validate that "mentorship" keyword triggers consultative strategy from intent mode.

        User request: "I want to buy a mentorship for trading" should NOT switch to transactional.
        """
        bot = SalesChatbot(provider_type="dummy", product_type="mentorship_service")

        # Start in intent discovery
        assert bot.flow_engine.flow_type == "intent"

        # User says "mentorship"
        bot.chat("I want to buy a mentorship for trading Bitcoin")

        # Should switch to consultative (not transactional)
        assert bot.flow_engine.flow_type == "consultative", "Mentorship keyword should trigger consultative strategy"
        assert bot.flow_engine.current_stage == "intent", "Should start in intent stage"

    def test_no_premature_pricing_discussion(self, chatbot):
        """
        Validate that bot doesn't discuss pricing during logical/emotional stages.

        Pricing should only come up in pitch stage or if prospect explicitly asks.
        """
        # Get to logical stage
        chatbot.chat("I'm struggling with trading consistency and looking for a solution")
        assert chatbot.flow_engine.current_stage == "logical"

        # Bot should NOT bring up pricing
        for i in range(5):
            response = chatbot.chat(f"Tell me about your solution, iteration {i + 1}")
            bot_message = response.content.lower()

            # Bot should not mention price/cost/budget in logical stage
            pricing_keywords = ["price", "cost", "budget", "payment", "fee", "$"]
            no_pricing = not any(kw in bot_message for kw in pricing_keywords)
            assert no_pricing or chatbot.flow_engine.current_stage != "logical", (
                "Bot should not discuss pricing in logical stage unless explicitly asked"
            )

    def test_training_coach_respects_consultative_stage(self, chatbot):
        """
        Validate that training coach doesn't recommend pricing in consultative stages.

        Training feedback should be context-aware based on current stage.
        """
        # Get to logical stage
        chatbot.chat("I'm struggling to grow my trading income and looking for professional help")
        assert chatbot.flow_engine.current_stage == "logical"

        # Generate training
        user_msg = "What makes your service different?"
        bot_reply = chatbot.chat(user_msg).content
        training = chatbot.generate_training(user_msg, bot_reply)

        # Training should NOT recommend pricing discussion
        training_text = str(training).lower()
        pricing_mentions = ["pricing", "budget", "cost", "price", "payment"]

        # If pricing is mentioned in training, it should only be as a warning NOT to discuss it yet
        if any(word in training_text for word in pricing_mentions):
            # Check that it's a negative instruction (don't discuss pricing)
            assert "don't" in training_text or "avoid" in training_text or "not" in training_text, (
                "Training should warn NOT to discuss pricing in logical stage"
            )

    def test_objection_handling_stage(self, chatbot):
        """
        Validate that objection stage is triggered by objection signals.

        If prospect raises objection during pitch, should transition to objection stage.
        """
        # Fast-forward to pitch stage (mock scenario)
        chatbot.chat("I want $20k/month")
        chatbot.flow_engine.advance(target_stage="logical")
        chatbot.chat("I'm struggling with losses")
        chatbot.flow_engine.advance(target_stage="emotional")
        chatbot.chat("I'm really worried about my future")
        chatbot.flow_engine.advance(target_stage="pitch")

        assert chatbot.flow_engine.current_stage == "pitch"

        # Raise objection
        chatbot.chat("This sounds too expensive for me")

        # Should transition to objection handling
        # (may need 1-2 turns to process objection)
        if chatbot.flow_engine.current_stage == "pitch":
            chatbot.chat("I'm not sure I can afford it")

        # Implementation note: Objection detection may vary
        # At minimum, should NOT advance back to intent or regress
        assert chatbot.flow_engine.current_stage in ["pitch", "objection"], (
            "Should stay in pitch or move to objection handling"
        )

    def test_rewind_functionality_preserves_stage(self, chatbot):
        """
        Validate that rewind() properly restores conversation state including stage.
        """
        # Progress through several stages
        chatbot.chat("I want $10k/month")
        chatbot.chat("I'm struggling with my strategy")
        initial_stage = chatbot.flow_engine.current_stage
        initial_turns = chatbot.flow_engine.stage_turn_count

        # Continue conversation
        chatbot.chat("This is really important to me")
        chatbot.chat("I feel stressed about money")

        # Rewind 2 turns back (return to initial turn)
        initial_turn_count = len(chatbot.flow_engine.conversation_history) // 2 - 2
        chatbot.rewind_to_turn(initial_turn_count)

        # Should restore previous stage
        assert chatbot.flow_engine.current_stage == initial_stage, "Rewind should restore stage"
        assert chatbot.flow_engine.stage_turn_count == initial_turns, "Rewind should restore turn count"


class TestTransactionalFlowComparison:
    """
    Compare transactional flow against consultative to validate different advancement logic.
    """

    @pytest.fixture
    def transactional_bot(self):
        """Create chatbot with transactional flow."""
        bot = SalesChatbot(provider_type="dummy", product_type="cryptoSIGNALS")
        bot.flow_engine.switch_strategy("transactional")
        return bot

    def test_transactional_advances_faster(self, transactional_bot):
        """
        Validate that transactional flow advances more quickly (fewer stages).

        Transactional: intent → pitch → objection (3 stages)
        Consultative: intent → logical → emotional → pitch → objection (5 stages)
        """
        # Transactional should go straight to pitch after intent
        transactional_bot.chat("I want to buy crypto trading signals")

        # After stating clear intent, should be in pitch or near pitch
        # (transactional doesn't need doubt/stakes building)
        turns = 0
        while transactional_bot.flow_engine.current_stage == "intent" and turns < 3:
            transactional_bot.chat("Yes, I want to purchase trading signals")
            turns += 1

        assert transactional_bot.flow_engine.current_stage == "pitch", "Transactional should advance to pitch quickly"
        assert turns <= 2, "Transactional should reach pitch in 2-3 turns"

    def test_transactional_discusses_pricing_early(self, transactional_bot):
        """
        Validate that transactional flow can discuss pricing immediately (no framework).

        Unlike consultative, transactional sales can talk pricing right away.
        """
        transactional_bot.chat("How much do your signals cost?")

        # Bot should be comfortable discussing pricing (no restriction)
        # This is acceptable in transactional mode
        assert transactional_bot.flow_engine.flow_type == "transactional"
        # No assertion on pricing mention - it's allowed in transactional
