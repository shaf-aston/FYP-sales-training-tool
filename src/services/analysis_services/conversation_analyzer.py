"""
Conversation Analyzer Component
Specialized analyzer for conversation metrics and flow analysis
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
import re
from collections import Counter

from .feedback_models import ConversationMetrics

logger = logging.getLogger(__name__)

class ConversationAnalyzer:
    """
    Specialized analyzer for conversation-level metrics and patterns
    Focuses on conversation flow, engagement, and basic interaction metrics
    """
    
    def __init__(self):
        """Initialize conversation analyzer"""
        self.engagement_keywords = [
            'interested', 'exciting', 'tell me more', 'really', 'wow', 
            'amazing', 'fantastic', 'great', 'excellent', 'perfect'
        ]
        
        self.disengagement_keywords = [
            'boring', 'not interested', 'maybe later', 'busy', 'hurry',
            'short on time', 'quick', 'brief', 'wrap up'
        ]
        
        self.question_starters = [
            'what', 'how', 'why', 'when', 'where', 'who', 'which',
            'can you', 'could you', 'would you', 'do you', 'are you',
            'is it', 'tell me', 'explain', 'describe'
        ]
        
        logger.info("✅ Conversation Analyzer initialized")
    
    def analyze(self, conversation_history: List[Dict]) -> ConversationMetrics:
        """
        Analyze conversation for basic metrics and flow patterns
        
        Args:
            conversation_history: List of conversation exchanges
            
        Returns:
            ConversationMetrics with analyzed data
        """
        try:
            if not conversation_history:
                return ConversationMetrics(
                    total_turns=0, user_turns=0, ai_turns=0, 
                    average_response_length=0.0, total_duration=0.0,
                    conversation_flow_score=0.0, engagement_score=0.0
                )
            
            logger.info(f"Analyzing conversation with {len(conversation_history)} exchanges")
            
            user_messages, ai_messages = self._extract_messages(conversation_history)
            
            basic_metrics = self._calculate_basic_metrics(user_messages, ai_messages)
            
            flow_score = self._analyze_conversation_flow(conversation_history)
            
            engagement_score = self._calculate_engagement_score(user_messages)
            
            total_duration = self._estimate_conversation_duration(user_messages, ai_messages)
            
            metrics = ConversationMetrics(
                total_turns=len(conversation_history),
                user_turns=len(user_messages),
                ai_turns=len(ai_messages),
                average_response_length=basic_metrics['avg_response_length'],
                total_duration=total_duration,
                conversation_flow_score=flow_score,
                engagement_score=engagement_score
            )
            
            logger.info(f"Conversation analysis complete: {metrics.total_turns} turns, "
                       f"flow score {flow_score:.2f}, engagement {engagement_score:.2f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Conversation analysis failed: {e}")
            return ConversationMetrics(
                total_turns=0, user_turns=0, ai_turns=0, 
                average_response_length=0.0, total_duration=0.0,
                conversation_flow_score=0.0, engagement_score=0.0
            )
    
    def _extract_messages(self, conversation_history: List[Dict]) -> Tuple[List[str], List[str]]:
        """Extract user and AI messages from conversation history"""
        user_messages = []
        ai_messages = []
        
        for exchange in conversation_history:
            if 'user_message' in exchange:
                user_messages.append(exchange['user_message'])
            elif 'user' in exchange:
                user_messages.append(exchange['user'])
            elif 'human' in exchange:
                user_messages.append(exchange['human'])
            
            if 'persona_response' in exchange:
                ai_messages.append(exchange['persona_response'])
            elif 'ai_response' in exchange:
                ai_messages.append(exchange['ai_response'])
            elif 'assistant' in exchange:
                ai_messages.append(exchange['assistant'])
            elif 'bot' in exchange:
                ai_messages.append(exchange['bot'])
        
        user_messages = [msg.strip() for msg in user_messages if msg and msg.strip()]
        ai_messages = [msg.strip() for msg in ai_messages if msg and msg.strip()]
        
        return user_messages, ai_messages
    
    def _calculate_basic_metrics(self, user_messages: List[str], ai_messages: List[str]) -> Dict[str, Any]:
        """Calculate basic conversation metrics"""
        all_messages = user_messages + ai_messages
        
        if not all_messages:
            return {'avg_response_length': 0.0}
        
        word_counts = [len(msg.split()) for msg in all_messages]
        avg_response_length = sum(word_counts) / len(word_counts)
        
        return {
            'avg_response_length': avg_response_length,
            'total_words': sum(word_counts),
            'user_word_count': sum(len(msg.split()) for msg in user_messages),
            'ai_word_count': sum(len(msg.split()) for msg in ai_messages)
        }
    
    def _analyze_conversation_flow(self, conversation_history: List[Dict]) -> float:
        """Analyze the natural flow and coherence of conversation"""
        if len(conversation_history) < 2:
            return 0.5
        
        flow_score = 0.5
        
        question_answer_pairs = 0
        follow_up_questions = 0
        
        for i, exchange in enumerate(conversation_history):
            user_msg = exchange.get('user_message', '').lower()
            
            if any(starter in user_msg for starter in self.question_starters):
                question_answer_pairs += 1
            
            if i > 0 and '?' in user_msg:
                prev_exchange = conversation_history[i-1]
                ai_response = prev_exchange.get('persona_response', '').lower()
                if len(ai_response.split()) > 5:
                    follow_up_questions += 1
        
        if conversation_history:
            qa_ratio = question_answer_pairs / len(conversation_history)
            flow_score += min(qa_ratio * 0.3, 0.2)
        
        if question_answer_pairs > 0:
            follow_up_ratio = follow_up_questions / question_answer_pairs
            flow_score += min(follow_up_ratio * 0.2, 0.15)
        
        if 5 <= len(conversation_history) <= 20:
            flow_score += 0.1
        elif len(conversation_history) > 20:
            flow_score += 0.15
        
        return min(flow_score, 1.0)
    
    def _calculate_engagement_score(self, user_messages: List[str]) -> float:
        """Calculate user engagement based on message content and patterns"""
        if not user_messages:
            return 0.0
        
        engagement_score = 0.3
        
        engagement_signals = 0
        disengagement_signals = 0
        
        for message in user_messages:
            message_lower = message.lower()
            
            engagement_signals += sum(1 for keyword in self.engagement_keywords 
                                    if keyword in message_lower)
            
            disengagement_signals += sum(1 for keyword in self.disengagement_keywords 
                                       if keyword in message_lower)
            
            if '?' in message:
                engagement_signals += 1
            
            word_count = len(message.split())
            if word_count > 15:
                engagement_signals += 1
            elif word_count < 3:
                disengagement_signals += 1
        
        total_messages = len(user_messages)
        positive_ratio = engagement_signals / (total_messages * 2)
        negative_ratio = disengagement_signals / (total_messages * 2)
        
        engagement_score += min(positive_ratio * 0.5, 0.4)
        engagement_score -= min(negative_ratio * 0.3, 0.2)
        
        if total_messages >= 5:
            engagement_score += 0.1
        
        return max(0.0, min(engagement_score, 1.0))
    
    def _estimate_conversation_duration(self, user_messages: List[str], ai_messages: List[str]) -> float:
        """Estimate conversation duration in minutes based on message length"""
        all_messages = user_messages + ai_messages
        
        if not all_messages:
            return 0.0
        
        total_words = sum(len(msg.split()) for msg in all_messages)
        
        message_processing_time = len(all_messages) * 0.5
        
        speaking_time = total_words / 150
        
        return speaking_time + (message_processing_time / 60)
    
    def get_conversation_insights(self, metrics: ConversationMetrics) -> Dict[str, Any]:
        """Generate insights and recommendations from conversation metrics"""
        insights = {
            'conversation_quality': 'good' if metrics.conversation_flow_score >= 0.7 else 
                                  'fair' if metrics.conversation_flow_score >= 0.5 else 'needs_improvement',
            'engagement_level': 'high' if metrics.engagement_score >= 0.7 else
                              'medium' if metrics.engagement_score >= 0.5 else 'low',
            'conversation_length': 'optimal' if 5 <= metrics.total_turns <= 15 else
                                 'too_short' if metrics.total_turns < 5 else 'too_long',
            'response_length': 'appropriate' if 10 <= metrics.average_response_length <= 30 else
                             'too_brief' if metrics.average_response_length < 10 else 'too_verbose'
        }
        
        recommendations = []
        
        if metrics.conversation_flow_score < 0.6:
            recommendations.append("Work on maintaining better conversation flow with follow-up questions")
        
        if metrics.engagement_score < 0.6:
            recommendations.append("Use more engaging language and show genuine interest")
        
        if metrics.total_turns < 5:
            recommendations.append("Try to extend conversations to gather more information")
        
        if metrics.average_response_length < 8:
            recommendations.append("Provide more detailed responses to show expertise")
        elif metrics.average_response_length > 35:
            recommendations.append("Keep responses more concise to maintain engagement")
        
        insights['recommendations'] = recommendations
        
        return insights