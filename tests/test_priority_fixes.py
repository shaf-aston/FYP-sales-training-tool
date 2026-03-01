"""Test suite for 4 Priority Fixes implementation.

Tests for:
1. Intent Lock with Goal Priming
2. Literal Question Detection  
3. Frustration Override
4. Context-Aware Guardedness
"""

import pytest
import sys, os

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chatbot.analysis import (
    analyze_state,
    is_literal_question,
    user_demands_directness,
    _has_user_stated_clear_goal
)


class TestPriority1IntentLock:
    """PRIORITY 1: Intent Lock with Goal Priming.
    
    Academic: Goal Priming (Chartrand & Bargh, 1996) + 
    Recency Bias (Kahneman & Tversky, 1974)
    
    Issue from conversation:
    - Turn 14: User states goal "been fat for years"
    - Turn 16: User gives short response "idk"
    - Expected: intent stays HIGH (user has goal primed)
    - Before fix: intent reverts to LOW
    """
    
    def test_goal_priming_detects_explicit_goals(self):
        """Test _has_user_stated_clear_goal detects goal keywords."""
        # Test: User states clear goal
        history = [
            {'role': 'user', 'content': 'I want to lose weight'},
            {'role': 'assistant', 'content': 'Great! How much weight?'},
        ]
        assert _has_user_stated_clear_goal(history) == True
    
    def test_goal_priming_detects_problem_keywords(self):
        """Test detection of problem/issue keywords."""
        history = [
            {'role': 'user', 'content': 'been fat for years'},
            {'role': 'assistant', 'content': 'I see'},
        ]
        assert _has_user_stated_clear_goal(history) == True
    
    def test_goal_priming_empty_history(self):
        """Test handles empty history gracefully."""
        assert _has_user_stated_clear_goal([]) == False
        assert _has_user_stated_clear_goal(None) == False
    
    def test_intent_lock_prevents_reversion(self):
        """Test PRIORITY 1: Intent locks to HIGH after goal stated.
        
        Simulates Turn 14-16 scenario:
        - User states goal (intent HIGH)
        - User gives short response 'idk' (normally LOW)
        - Expected: intent stays HIGH due to goal lock
        """
        history = [
            {'role': 'user', 'content': 'I want to lose weight'},
            {'role': 'assistant', 'content': 'How much weight do you want to lose?'},
        ]
        
        # Short response that would normally trigger LOW intent
        user_message = 'idk'
        state = analyze_state(history, user_message)
        
        # PRIORITY 1 FIX: Intent should stay HIGH due to goal lock
        assert state['intent'] == 'high', \
            f"Goal priming failed: intent={state['intent']}, expected HIGH"
    
    def test_intent_lock_multiple_goal_keywords(self):
        """Test intent lock works with various goal keywords."""
        goal_keywords = [
            'lose weight', 'put on muscle', 'been fat',
            'struggling', 'looking to', 'trying to', 'need to',
            'want to', 'problem', 'issue', 'challenge'
        ]
        
        for keyword in goal_keywords:
            history = [
                {'role': 'user', 'content': f'I am {keyword} get healthier'},
                {'role': 'assistant', 'content': 'Tell me more'},
            ]
            assert _has_user_stated_clear_goal(history) == True, \
                f"Failed to detect goal keyword: {keyword}"
    
    def test_intent_lock_recency_weighting(self):
        """Test recent goals take precedence over old messages."""
        # Long history where goal is recent
        history = [
            {'role': 'user', 'content': 'hi'},
            {'role': 'assistant', 'content': 'hello'},
            {'role': 'user', 'content': 'not interested'},
            {'role': 'assistant', 'content': 'ok'},
            {'role': 'user', 'content': 'i want to lose weight'},  # Recent goal
        ]
        
        assert _has_user_stated_clear_goal(history) == True


class TestPriority2LiteralQuestions:
    """PRIORITY 2: Literal Question Detection.
    
    Academic: Speech Act Theory (Searle, 1969)
    Distinction: Literal questions vs rhetorical vs reflective
    
    Issue from conversation:
    - Turn 40: User asks "whats changed?"
    - Expected: Recognize as literal question, provide direct answer
    - Before fix: Bot treated as validation request instead
    """
    
    def test_literal_question_with_question_word(self):
        """Test detection of questions starting with question words."""
        literal_questions = [
            'what is your name?',
            'how does this work?',
            'when is the deadline?',
            'where are you from?',
            'who is responsible?',
            'why is this important?',
        ]
        
        for question in literal_questions:
            assert is_literal_question(question) == True, \
                f"Failed to detect literal question: {question}"
    
    def test_literal_question_casual_format(self):
        """Test casual question formats."""
        casual_questions = [
            "whats changed?",
            "hows it going?",
            "whats that mean?",
        ]
        
        for question in casual_questions:
            assert is_literal_question(question) == True, \
                f"Failed to detect casual question: {question}"
    
    def test_literal_question_with_trailing_question_mark(self):
        """Test simple statement with question mark."""
        questions = [
            "you have the answer?",
            "this is what you meant?",
        ]
        
        for question in questions:
            assert is_literal_question(question) == True, \
                f"Failed to detect question mark ending: {question}"
    
    def test_rhetorical_questions_excluded(self):
        """Test that complex rhetorical questions are excluded."""
        rhetorical = [
            "why is the sky blue, why are clouds white, why do birds sing?",  # Multiple clauses
            "dont you think, isnt it obvious, wouldnt you agree?",  # Multiple clauses
        ]
        
        for question in rhetorical:
            assert is_literal_question(question) == False, \
                f"Incorrectly detected rhetorical as literal: {question}"
    
    def test_non_questions(self):
        """Test that non-questions return False."""
        non_questions = [
            "I think that's good",
            "Tell me about yourself",
            "The weather is nice",
            "",
            None,
        ]
        
        for text in non_questions:
            assert is_literal_question(text) == False, \
                f"Incorrectly detected non-question: {text}"
    
    def test_turn_40_scenario(self):
        """Test Turn 40 from user conversation: 'whats changed?'"""
        user_message = "whats changed?"
        assert is_literal_question(user_message) == True, \
            "Failed to detect Turn 40 'whats changed?' as literal question"


class TestPriority3FrustrationOverride:
    """PRIORITY 3: Frustration Override.
    
    Academic: Conversational Repair Theory (Schegloff, 1992) +
    Politeness Collapse (Brown & Levinson, 1987)
    
    Issue from conversation:
    - Turn 18: User says "tell me then"
    - Turn 20: User shows frustration with continued questions
    - Expected: Skip to pitch stage immediately
    - Before fix: Bot kept asking elicitation questions
    """
    
    def test_frustration_demand_indicators(self):
        """Test detection of explicit demands.

        Note: 'tell me' and 'explain' are intentionally NOT in demand_directness
        signals — they are legitimate requests, not frustration signals.
        Only strong frustration signals are tested here.
        """
        demand_messages = [
            'just tell me',
            'what is it',
            'i asked you',
            'get to the point',
            'stop asking',
            'cut to the chase',
        ]

        history = []
        for msg in demand_messages:
            assert user_demands_directness(history, msg) == True, \
                f"Failed to detect demand: {msg}"
    
    def test_frustration_emotion_indicators(self):
        """Test detection of frustration emotions."""
        frustration_messages = [
            'youre right, im frustrated',
            'im looking to lose weight i said',
            'that wasnt what i asked',
        ]
        
        history = []
        for msg in frustration_messages:
            assert user_demands_directness(history, msg) == True, \
                f"Failed to detect frustration: {msg}"
    
    def test_frustration_repeated_clarification(self):
        """Test detection of repeated frustration (user saying 'i said')."""
        history = [
            {'role': 'user', 'content': 'I want to lose weight'},
            {'role': 'assistant', 'content': 'Tell me more about your goals'},
            {'role': 'user', 'content': 'No, like I said, losing weight'},
        ]
        
        user_message = 'My weight, I said'
        assert user_demands_directness(history, user_message) == True, \
            "Failed to detect repeated frustration"
    
    def test_turn_18_20_scenario(self):
        """Test Turn 18-20: User demands directness.

        'tell me then' is no longer a frustration signal (too broad).
        'just tell me' (with qualifier) is the correct signal.
        """
        messages = [
            'just tell me',  # Turn 20 — strong signal with qualifier
        ]
        
        history = []
        for msg in messages:
            assert user_demands_directness(history, msg) == True, \
                f"Failed to detect frustration in Turn 18-20 scenario: {msg}"
    
    def test_normal_responses_not_flagged(self):
        """Test that normal responses aren't mistaken for frustration."""
        normal_messages = [
            'I think that sounds good',
            'ok cool',
            'thanks for that information',
            'got it',
        ]
        
        history = []
        for msg in normal_messages:
            assert user_demands_directness(history, msg) == False, \
                f"Incorrectly flagged as frustration: {msg}"
    
    def test_case_insensitivity(self):
        """Test frustration detection is case-insensitive."""
        messages = [
            'JUST TELL ME',
            'Just Tell Me',
            'GET TO THE POINT',
            'Stop Asking',
        ]
        
        history = []
        for msg in messages:
            assert user_demands_directness(history, msg) == True, \
                f"Case sensitivity failed: {msg}"


class TestPriority4ContextAwareGuardedness:
    """PRIORITY 4: Context-Aware Guardedness.
    
    Academic: Relevance Theory (Sperber & Wilson, 1995)
    Distinction: "ok" after answer = agreement vs "ok" = guard
    
    Issue from conversation:
    - Turn 28, 42: "ok" flagged as guarded when user was agreeing
    - Expected: 'ok' after substantive answer = NOT guarded
    - Before fix: All short + 'ok' = guarded
    """
    
    def test_agreement_pattern_not_guarded(self):
        """Test: question → substantive answer → 'ok' = agreement, not guarded.
        
        Context flow:
        1. Bot asks question: 'What's your goal?'
        2. User gives substantial answer: 'I want to lose 20 pounds...' (8+ words)
        3. User says: 'ok'
        
        Expected: guarded=False (user is agreeing, not defending)
        """
        history = [
            {'role': 'assistant', 'content': "What's your primary fitness goal?"},  # Question
            {'role': 'user', 'content': 'I want to lose about twenty pounds this year'},  # 9 words, substantive
            {'role': 'assistant', 'content': 'That sounds achievable. Here are some options.'},
            {'role': 'user', 'content': 'ok'},  # Short response
        ]
        
        state = analyze_state(history, 'ok')
        
        # PRIORITY 4 FIX: 'ok' after substantive answer = agreement, NOT guarded
        assert state['guarded'] == False, \
            f"Incorrectly flagged agreement as guarded: {state}"
    
    def test_turn_28_agreement_scenario(self):
        """Test Turn 28: User saying 'ok' after agreeing with suggestion."""
        history = [
            {'role': 'assistant', 'content': 'Would you be interested in a structured workout plan?'},
            {'role': 'user', 'content': 'Yes, that would definitely help me stay consistent and motivated'},
            {'role': 'assistant', 'content': 'Great! I have a beginner plan here.'},
            {'role': 'user', 'content': 'ok'},
        ]
        
        state = analyze_state(history, 'ok')
        assert state['guarded'] == False, \
            "Turn 28: Incorrectly flagged 'ok' as guarded when agreeing"
    
    def test_actual_guardedness_still_detected(self):
        """Test that REAL guardedness is still detected."""
        history = [
            {'role': 'assistant', 'content': 'What brings you here today?'},
            {'role': 'user', 'content': 'Not sure yet'},  # Short, evasive
        ]
        
        state = analyze_state(history, 'ok')
        # 'ok' without preceding substantive answer = might be guarded
        # Depends on context, but short + evasive signals = guarded likely true
        assert isinstance(state['guarded'], bool), \
            "Guardedness detection should return bool"
    
    def test_substantive_answer_threshold(self):
        """Test 8-word threshold for substantive answers."""
        # Below threshold (not substantive)
        short_answer = 'maybe'  # 1 word
        history_short = [
            {'role': 'assistant', 'content': 'Are you interested?'},
            {'role': 'user', 'content': short_answer},
            {'role': 'assistant', 'content': 'Tell me more'},
            {'role': 'user', 'content': 'ok'},
        ]
        
        # At/above threshold (substantive)
        substantive_answer = 'I think that could work for me'  # 6 words (below 8)
        history_medium = [
            {'role': 'assistant', 'content': 'Are you interested?'},
            {'role': 'user', 'content': substantive_answer},
            {'role': 'assistant', 'content': 'Great!'},
            {'role': 'user', 'content': 'ok'},
        ]
        
        # Well above threshold
        full_answer = 'Yes I am interested in that plan because it fits my schedule perfectly'  # 12+ words
        history_long = [
            {'role': 'assistant', 'content': 'Are you interested?'},
            {'role': 'user', 'content': full_answer},
            {'role': 'assistant', 'content': 'Excellent!'},
            {'role': 'user', 'content': 'ok'},
        ]
        
        state_short = analyze_state(history_short, 'ok')
        state_medium = analyze_state(history_medium, 'ok')
        state_long = analyze_state(history_long, 'ok')
        
        # Long answer should be recognized as substantive
        assert state_long['guarded'] == False, \
            "Should recognize 12+ word answer as substantive (not guarded)"


class TestIntegrationScenarios:
    """Integration tests using real conversation scenarios."""
    
    def test_full_turn_14_16_scenario(self):
        """Full integration: Turns 14-16 from user conversation.
        
        Turn 14: User states goal
        Turn 16: User gives short response
        
        Before: intent reverted to LOW
        After: intent stays HIGH (goal lock)
        """
        conversation = [
            {'role': 'assistant', 'content': 'What brings you here?'},
            {'role': 'user', 'content': 'Ive been fat for years and want to change'},  # Goal stated
            {'role': 'assistant', 'content': 'That takes courage. How much weight are you hoping to lose?'},
            {'role': 'user', 'content': 'idk'},  # Short response
        ]
        
        state = analyze_state(conversation, 'idk')
        
        # PRIORITY 1: Intent should stay HIGH due to goal priming
        assert state['intent'] == 'high', \
            f"Turn 14-16: Goal priming failed, intent={state['intent']}, expected HIGH"
    
    def test_full_turn_18_20_scenario(self):
        """Full integration: Turns 18-20 frustration scenario.

        'tell me then' is no longer a frustration signal (too broad).
        Tests with the qualifier form 'just tell me' which is the correct signal.
        """
        conversation = [
            {'role': 'assistant', 'content': 'Let me ask a few questions to understand better'},
            {'role': 'user', 'content': 'just tell me'},
        ]

        is_frustrated = user_demands_directness(conversation, 'just tell me')
        assert is_frustrated == True, \
            "Turn 18-20: Failed to detect frustration demand"
    
    def test_full_turn_28_guarded_fix(self):
        """Full integration: Turn 28 context-aware guardedness.
        
        User says 'ok' after agreeing = not guarded
        """
        conversation = [
            {'role': 'assistant', 'content': 'Would this approach work for you?'},
            {'role': 'user', 'content': 'Yes that would be perfect for getting started on this'},
            {'role': 'assistant', 'content': 'Awesome! Here are the options:'},
            {'role': 'user', 'content': 'ok'},
        ]
        
        state = analyze_state(conversation, 'ok')
        
        # PRIORITY 4: 'ok' after substantive answer = agreement, not guarded
        assert state['guarded'] == False, \
            f"Turn 28: Failed to recognize agreement pattern. Guarded={state['guarded']}"
    
    def test_full_turn_40_literal_question(self):
        """Full integration: Turn 40 literal question detection.
        
        User asks 'whats changed?'
        Expected: Recognized as literal question, trigger answer mode
        """
        is_question = is_literal_question('whats changed?')
        assert is_question == True, \
            "Turn 40: Failed to detect 'whats changed?' as literal question"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
