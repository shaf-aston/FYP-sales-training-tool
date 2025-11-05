"""
Communication Analyzer Component
Specialized analyzer for communication style and effectiveness
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import Counter

from .feedback_models import CommunicationAnalysis, CommunicationStyle

logger = logging.getLogger(__name__)

class CommunicationAnalyzer:
    """
    Specialized analyzer for communication patterns, style, and effectiveness
    Focuses on tone, question types, language patterns, and communication quality
    """
    
    def __init__(self):
        """Initialize communication analyzer"""
        self.professional_indicators = [
            "please", "thank you", "appreciate", "understand", "certainly",
            "absolutely", "definitely", "excellent", "pleasure", "grateful"
        ]
        
        self.casual_indicators = [
            "yeah", "sure thing", "no worries", "awesome", "cool",
            "hey", "hi there", "okay", "alright", "totally"
        ]
        
        self.empathetic_indicators = [
            "i understand", "that makes sense", "i can see", "i hear you",
            "that must be", "i appreciate", "i realize", "i see your point"
        ]
        
        self.assertive_indicators = [
            "definitely", "absolutely", "confident", "guarantee", "ensure",
            "certainly", "definitely", "absolutely", "without question"
        ]
        
        self.question_starters = [
            "what", "how", "why", "when", "where", "who", "which",
            "can you", "could you", "would you", "do you", "are you",
            "is it", "tell me", "explain", "describe"
        ]
        
        logger.info("✅ Communication Analyzer initialized")
    
    def analyze(self, conversation_history: List[Dict]) -> CommunicationAnalysis:
        """
        Analyze communication style and effectiveness
        
        Args:
            conversation_history: List of conversation exchanges
            
        Returns:
            CommunicationAnalysis with detailed style breakdown
        """
        try:
            if not conversation_history:
                return CommunicationAnalysis(
                    dominant_style=CommunicationStyle.PASSIVE,
                    style_scores={},
                    question_analysis={},
                    language_patterns={},
                    effectiveness_rating="insufficient_data"
                )
            
            logger.info(f"Analyzing communication patterns in {len(conversation_history)} exchanges")
            
            # Extract user messages
            user_messages = self._extract_user_messages(conversation_history)
            
            # Analyze style scores
            style_scores = self._calculate_style_scores(user_messages)
            
            # Determine dominant style
            dominant_style = self._determine_dominant_style(style_scores)
            
            # Analyze question patterns
            question_analysis = self._analyze_question_patterns(user_messages)
            
            # Analyze language patterns
            language_patterns = self._analyze_language_patterns(user_messages)
            
            # Rate overall effectiveness
            effectiveness_rating = self._rate_communication_effectiveness(
                style_scores, question_analysis, language_patterns
            )
            
            analysis = CommunicationAnalysis(
                dominant_style=dominant_style,
                style_scores=style_scores,
                question_analysis=question_analysis,
                language_patterns=language_patterns,
                effectiveness_rating=effectiveness_rating
            )
            
            logger.info(f"Communication analysis complete: dominant style {dominant_style.value}, "
                       f"effectiveness {effectiveness_rating}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Communication analysis failed: {e}")
            return CommunicationAnalysis(
                dominant_style=CommunicationStyle.PASSIVE,
                style_scores={},
                question_analysis={},
                language_patterns={},
                effectiveness_rating="error"
            )
    
    def _extract_user_messages(self, conversation_history: List[Dict]) -> List[str]:
        """Extract user messages from conversation history"""
        user_messages = []
        
        for exchange in conversation_history:
            # Handle different message formats
            if 'user_message' in exchange:
                user_messages.append(exchange['user_message'])
            elif 'user' in exchange:
                user_messages.append(exchange['user'])
            elif 'human' in exchange:
                user_messages.append(exchange['human'])
        
        # Clean and filter messages
        user_messages = [msg.strip() for msg in user_messages if msg and msg.strip()]
        
        return user_messages
    
    def _calculate_style_scores(self, user_messages: List[str]) -> Dict[str, float]:
        """Calculate scores for different communication styles"""
        if not user_messages:
            return {
                'professional': 0.0, 'casual': 0.0, 'empathetic': 0.0, 'assertive': 0.0
            }
        
        total_messages = len(user_messages)
        style_counts = {
            'professional': 0,
            'casual': 0,
            'empathetic': 0,
            'assertive': 0
        }
        
        for message in user_messages:
            message_lower = message.lower()
            
            # Count style indicators
            if any(word in message_lower for word in self.professional_indicators):
                style_counts['professional'] += 1
            
            if any(word in message_lower for word in self.casual_indicators):
                style_counts['casual'] += 1
            
            if any(phrase in message_lower for phrase in self.empathetic_indicators):
                style_counts['empathetic'] += 1
            
            if any(word in message_lower for word in self.assertive_indicators):
                style_counts['assertive'] += 1
        
        # Convert to percentages
        style_scores = {
            style: (count / total_messages) * 100
            for style, count in style_counts.items()
        }
        
        return style_scores
    
    def _determine_dominant_style(self, style_scores: Dict[str, float]) -> CommunicationStyle:
        """Determine the dominant communication style"""
        if not style_scores:
            return CommunicationStyle.PASSIVE
        
        # Find style with highest score
        dominant_name = max(style_scores.keys(), key=lambda k: style_scores[k])
        
        # Map to CommunicationStyle enum
        style_mapping = {
            'professional': CommunicationStyle.ASSERTIVE,  # Professional maps to assertive
            'casual': CommunicationStyle.RELATIONSHIP_FOCUSED,  # Casual maps to relationship-focused
            'empathetic': CommunicationStyle.RELATIONSHIP_FOCUSED,  # Empathetic maps to relationship-focused
            'assertive': CommunicationStyle.ASSERTIVE  # Assertive stays assertive
        }
        
        return style_mapping.get(dominant_name, CommunicationStyle.PASSIVE)
    
    def _analyze_question_patterns(self, user_messages: List[str]) -> Dict[str, Any]:
        """Analyze question asking patterns and effectiveness"""
        if not user_messages:
            return {
                'open_questions': 0,
                'closed_questions': 0,
                'question_ratio': 0.0,
                'question_quality': 'insufficient_data'
            }
        
        open_questions = 0
        closed_questions = 0
        
        for message in user_messages:
            message_lower = message.lower()
            
            # Count questions
            if '?' in message:
                # Check if it's an open-ended question
                if any(starter in message_lower for starter in self.question_starters):
                    open_questions += 1
                else:
                    closed_questions += 1
        
        total_questions = open_questions + closed_questions
        
        if total_questions == 0:
            question_ratio = 0.0
            quality = 'no_questions_asked'
        else:
            question_ratio = (open_questions / total_questions) * 100
            
            # Determine quality based on ratio
            if question_ratio >= 70:
                quality = 'excellent_open_focused'
            elif question_ratio >= 50:
                quality = 'good_balance'
            elif question_ratio >= 30:
                quality = 'adequate'
            else:
                quality = 'too_closed_focused'
        
        return {
            'open_questions': open_questions,
            'closed_questions': closed_questions,
            'question_ratio': round(question_ratio, 1),
            'question_quality': quality,
            'questions_per_message': round(total_questions / len(user_messages), 2)
        }
    
    def _analyze_language_patterns(self, user_messages: List[str]) -> Dict[str, Any]:
        """Analyze language patterns and communication quality indicators"""
        if not user_messages:
            return {
                'average_word_count': 0,
                'vocabulary_richness': 0,
                'positive_language_ratio': 0.0,
                'professional_language_ratio': 0.0
            }
        
        # Calculate word statistics
        all_words = []
        total_chars = 0
        
        for message in user_messages:
            words = message.split()
            all_words.extend(words)
            total_chars += len(message)
        
        # Basic statistics
        total_words = len(all_words)
        unique_words = len(set(word.lower() for word in all_words))
        avg_words_per_message = total_words / len(user_messages)
        avg_chars_per_message = total_chars / len(user_messages)
        
        # Vocabulary richness (unique words / total words)
        vocabulary_richness = (unique_words / total_words) * 100 if total_words > 0 else 0
        
        # Positive language analysis
        positive_words = [
            'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'perfect',
            'good', 'better', 'best', 'love', 'like', 'enjoy', 'happy', 'pleased'
        ]
        
        positive_count = sum(1 for word in all_words 
                           if word.lower() in positive_words)
        positive_ratio = (positive_count / total_words) * 100 if total_words > 0 else 0
        
        # Professional language analysis
        professional_count = sum(1 for word in all_words 
                               if word.lower() in self.professional_indicators)
        professional_ratio = (professional_count / total_words) * 100 if total_words > 0 else 0
        
        # Sentence structure analysis
        sentences_with_questions = sum(1 for msg in user_messages if '?' in msg)
        sentences_with_exclamation = sum(1 for msg in user_messages if '!' in msg)
        
        return {
            'average_word_count': round(avg_words_per_message, 1),
            'average_char_count': round(avg_chars_per_message, 1),
            'vocabulary_richness': round(vocabulary_richness, 1),
            'positive_language_ratio': round(positive_ratio, 1),
            'professional_language_ratio': round(professional_ratio, 1),
            'engagement_indicators': {
                'questions_used': sentences_with_questions,
                'exclamation_used': sentences_with_exclamation,
                'question_percentage': round((sentences_with_questions / len(user_messages)) * 100, 1),
                'exclamation_percentage': round((sentences_with_exclamation / len(user_messages)) * 100, 1)
            }
        }
    
    def _rate_communication_effectiveness(self, style_scores: Dict[str, float], 
                                        question_analysis: Dict[str, Any],
                                        language_patterns: Dict[str, Any]) -> str:
        """Rate overall communication effectiveness"""
        score = 0
        
        # Style balance (20 points max)
        total_style_score = sum(style_scores.values())
        if total_style_score >= 80:  # Good style presence
            score += 20
        elif total_style_score >= 50:
            score += 15
        elif total_style_score >= 25:
            score += 10
        
        # Question quality (30 points max)
        question_ratio = question_analysis.get('question_ratio', 0)
        if question_ratio >= 60:  # Good balance of open/closed questions
            score += 30
        elif question_ratio >= 40:
            score += 20
        elif question_ratio >= 20:
            score += 10
        
        # Language quality (25 points max)
        vocab_richness = language_patterns.get('vocabulary_richness', 0)
        if vocab_richness >= 40:  # Good vocabulary diversity
            score += 15
        
        professional_ratio = language_patterns.get('professional_language_ratio', 0)
        if professional_ratio >= 10:  # Appropriate professional language
            score += 10
        
        # Engagement indicators (25 points max)
        engagement = language_patterns.get('engagement_indicators', {})
        question_pct = engagement.get('question_percentage', 0)
        exclamation_pct = engagement.get('exclamation_percentage', 0)
        
        if question_pct >= 20:  # Good questioning engagement
            score += 15
        elif question_pct >= 10:
            score += 10
        
        if exclamation_pct >= 5:  # Appropriate enthusiasm
            score += 10
        
        # Convert score to rating
        if score >= 80:
            return "excellent"
        elif score >= 65:
            return "good"
        elif score >= 50:
            return "adequate"
        elif score >= 35:
            return "needs_improvement"
        else:
            return "poor"
    
    def get_communication_insights(self, analysis: CommunicationAnalysis) -> Dict[str, Any]:
        """Generate insights and recommendations from communication analysis"""
        insights = {
            'style_profile': f"Dominant style: {analysis.dominant_style.value}",
            'strengths': [],
            'improvement_areas': [],
            'recommendations': []
        }
        
        # Analyze strengths
        if analysis.style_scores.get('professional', 0) > 60:
            insights['strengths'].append("Strong professional communication")
        
        if analysis.style_scores.get('empathetic', 0) > 60:
            insights['strengths'].append("Excellent empathetic responses")
        
        if analysis.question_analysis.get('question_ratio', 0) > 60:
            insights['strengths'].append("Effective use of open-ended questions")
        
        # Analyze improvement areas
        if analysis.style_scores.get('professional', 0) < 30:
            insights['improvement_areas'].append("Professional tone could be stronger")
            insights['recommendations'].append("Use more courteous language like 'please', 'thank you', 'I appreciate'")
        
        if analysis.style_scores.get('empathetic', 0) < 30:
            insights['improvement_areas'].append("Empathy indicators are low")
            insights['recommendations'].append("Show more understanding with phrases like 'I understand' or 'That makes sense'")
        
        question_ratio = analysis.question_analysis.get('question_ratio', 0)
        if question_ratio < 40:
            insights['improvement_areas'].append("Too many closed-ended questions")
            insights['recommendations'].append("Ask more open-ended questions starting with 'what', 'how', 'why'")
        
        vocab_richness = analysis.language_patterns.get('vocabulary_richness', 0)
        if vocab_richness < 30:
            insights['improvement_areas'].append("Limited vocabulary variety")
            insights['recommendations'].append("Use more diverse language to show expertise and engagement")
        
        return insights