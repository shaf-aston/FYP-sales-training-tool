"""
Emotional Intelligence Analyzer Component
Specialized analyzer for emotional intelligence and rapport building
"""

import logging
from typing import Dict, List, Optional, Any, Tuple

from .feedback_models import EmotionalIntelligenceAnalysis

logger = logging.getLogger(__name__)

class EmotionalIntelligenceAnalyzer:
    """
    Specialized analyzer for emotional intelligence in sales conversations
    Focuses on empathy, rapport building, adaptability, and emotional awareness
    """
    
    def __init__(self):
        """Initialize emotional intelligence analyzer"""
        self.empathy_indicators = [
            "i understand", "that makes sense", "i can see", "i hear you",
            "that must be", "i appreciate", "i realize", "i see your point",
            "that sounds", "i get that", "makes perfect sense"
        ]
        
        self.emotional_awareness_keywords = [
            "excited", "worried", "concerned", "frustrated", "happy",
            "pleased", "disappointed", "relieved", "confused", "overwhelmed",
            "stressed", "anxious", "enthusiastic", "optimistic", "pessimistic"
        ]
        
        self.rapport_building_phrases = [
            "tell me more", "that's interesting", "i'm curious", "fascinating",
            "that's a great point", "i agree", "absolutely", "exactly",
            "you make a good point", "that's a valid concern"
        ]
        
        self.adaptability_indicators = [
            "based on what you've said", "i hear that you", "sounds like you",
            "it seems you", "i understand you", "you mentioned", "you said",
            "from what you've shared", "i see that you", "you seem to"
        ]
        
        logger.info("✅ Emotional Intelligence Analyzer initialized")
    
    def analyze(self, conversation_history: List[Dict], persona_data: Optional[Dict] = None) -> EmotionalIntelligenceAnalysis:
        """
        Analyze emotional intelligence in the conversation
        
        Args:
            conversation_history: List of conversation exchanges
            persona_data: Optional persona information for context
            
        Returns:
            EmotionalIntelligenceAnalysis with detailed EQ breakdown
        """
        try:
            if not conversation_history:
                return EmotionalIntelligenceAnalysis(
                    empathy_score=0.0,
                    rapport_score=0.0,
                    adaptability_score=0.0,
                    overall_eq_score=0.0,
                    eq_rating="insufficient_data",
                    strengths=[],
                    improvement_areas=[]
                )
            
            logger.info(f"Analyzing emotional intelligence in {len(conversation_history)} exchanges")
            
            # Extract messages
            user_messages, ai_messages = self._extract_messages(conversation_history)
            
            # Calculate empathy score
            empathy_score = self._calculate_empathy_score(user_messages)
            
            # Calculate rapport score
            rapport_score = self._calculate_rapport_score(user_messages)
            
            # Calculate adaptability score
            adaptability_score = self._calculate_adaptability_score(user_messages, persona_data)
            
            # Calculate emotional awareness
            emotional_awareness_score = self._calculate_emotional_awareness(user_messages, ai_messages)
            
            # Calculate overall EQ score
            overall_eq_score = self._calculate_overall_eq_score(
                empathy_score, rapport_score, adaptability_score, emotional_awareness_score
            )
            
            # Determine EQ rating
            eq_rating = self._rate_emotional_intelligence(overall_eq_score)
            
            # Identify strengths and improvement areas
            strengths, improvement_areas = self._identify_eq_strengths_and_gaps(
                empathy_score, rapport_score, adaptability_score, emotional_awareness_score
            )
            
            analysis = EmotionalIntelligenceAnalysis(
                empathy_score=empathy_score,
                rapport_score=rapport_score,
                adaptability_score=adaptability_score,
                overall_eq_score=overall_eq_score,
                eq_rating=eq_rating,
                strengths=strengths,
                improvement_areas=improvement_areas
            )
            
            logger.info(f"EQ analysis complete: overall score {overall_eq_score:.1f}, "
                       f"rating {eq_rating}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Emotional intelligence analysis failed: {e}")
            return EmotionalIntelligenceAnalysis(
                empathy_score=0.0,
                rapport_score=0.0,
                adaptability_score=0.0,
                overall_eq_score=0.0,
                eq_rating="error",
                strengths=[],
                improvement_areas=["Analysis failed"]
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
        
        # Clean messages
        user_messages = [msg.strip() for msg in user_messages if msg and msg.strip()]
        ai_messages = [msg.strip() for msg in ai_messages if msg and msg.strip()]
        
        return user_messages, ai_messages
    
    def _calculate_empathy_score(self, user_messages: List[str]) -> float:
        """Calculate empathy score based on empathetic language usage"""
        if not user_messages:
            return 0.0
        
        total_messages = len(user_messages)
        empathy_signals = 0
        
        for message in user_messages:
            message_lower = message.lower()
            
            # Count empathy indicators
            if any(phrase in message_lower for phrase in self.empathy_indicators):
                empathy_signals += 1
        
        # Calculate percentage and scale to 0-100
        empathy_ratio = empathy_signals / total_messages
        empathy_score = min(empathy_ratio * 100, 100.0)
        
        return empathy_score
    
    def _calculate_rapport_score(self, user_messages: List[str]) -> float:
        """Calculate rapport building score"""
        if not user_messages:
            return 0.0
        
        total_messages = len(user_messages)
        rapport_signals = 0
        
        for message in user_messages:
            message_lower = message.lower()
            
            # Count rapport building phrases
            if any(phrase in message_lower for phrase in self.rapport_building_phrases):
                rapport_signals += 1
        
        # Calculate percentage and scale to 0-100
        rapport_ratio = rapport_signals / total_messages
        rapport_score = min(rapport_ratio * 150, 100.0)  # Rapport phrases are less common, so scale up
        
        return rapport_score
    
    def _calculate_adaptability_score(self, user_messages: List[str], persona_data: Optional[Dict]) -> float:
        """Calculate adaptability score based on persona-specific responses"""
        if not user_messages or not persona_data:
            # Calculate basic adaptability from general indicators
            adaptability_signals = 0
            total_messages = len(user_messages)
            
            for message in user_messages:
                message_lower = message.lower()
                if any(phrase in message_lower for phrase in self.adaptability_indicators):
                    adaptability_signals += 1
            
            adaptability_ratio = adaptability_signals / total_messages if total_messages > 0 else 0
            return min(adaptability_ratio * 100, 100.0)
        
        # Persona-specific adaptability analysis
        persona_traits = persona_data.get("personality_traits", [])
        persona_concerns = persona_data.get("concerns", [])
        
        trait_adaptation_score = self._calculate_trait_adaptation(user_messages, persona_traits)
        concern_adaptation_score = self._calculate_concern_adaptation(user_messages, persona_concerns)
        
        # Combine scores
        adaptability_score = (trait_adaptation_score + concern_adaptation_score) / 2
        
        return adaptability_score
    
    def _calculate_trait_adaptation(self, user_messages: List[str], persona_traits: List[str]) -> float:
        """Calculate how well the user adapted to persona traits"""
        if not persona_traits:
            return 50.0  # Neutral score if no traits specified
        
        adaptation_signals = 0
        all_text = ' '.join(user_messages).lower()
        
        for trait in persona_traits:
            trait_lower = trait.lower()
            
            # Check for trait-specific adaptation
            if trait_lower == "cautious":
                if any(word in all_text for word in ["safe", "careful", "gradually", "step by step", "comfortable"]):
                    adaptation_signals += 1
            elif trait_lower == "analytical":
                if any(word in all_text for word in ["data", "evidence", "research", "studies", "facts", "logic"]):
                    adaptation_signals += 1
            elif trait_lower == "budget-conscious":
                if any(word in all_text for word in ["affordable", "value", "cost-effective", "budget", "investment"]):
                    adaptation_signals += 1
            elif trait_lower == "relationship-focused":
                if any(word in all_text for word in ["team", "together", "relationship", "partnership", "connection"]):
                    adaptation_signals += 1
            elif trait_lower == "detail-oriented":
                if any(word in all_text for word in ["specific", "details", "particular", "exactly", "precise"]):
                    adaptation_signals += 1
        
        adaptation_ratio = adaptation_signals / len(persona_traits)
        return min(adaptation_ratio * 100, 100.0)
    
    def _calculate_concern_adaptation(self, user_messages: List[str], persona_concerns: List[str]) -> float:
        """Calculate how well the user addressed persona concerns"""
        if not persona_concerns:
            return 50.0  # Neutral score if no concerns specified
        
        concern_addressed = 0
        all_text = ' '.join(user_messages).lower()
        
        for concern in persona_concerns:
            concern_words = concern.lower().split()
            # Check if any concern-related words appear in user messages
            if any(word in all_text for word in concern_words):
                concern_addressed += 1
        
        concern_ratio = concern_addressed / len(persona_concerns)
        return min(concern_ratio * 100, 100.0)
    
    def _calculate_emotional_awareness(self, user_messages: List[str], ai_messages: List[str]) -> float:
        """Calculate emotional awareness based on emotional responses and tone matching"""
        if not user_messages or not ai_messages:
            return 0.0
        
        emotional_responses = 0
        tone_matching = 0
        
        # Analyze AI emotional responses
        for ai_msg in ai_messages:
            ai_lower = ai_msg.lower()
            if any(word in ai_lower for word in self.emotional_awareness_keywords):
                emotional_responses += 1
        
        # Analyze tone matching (user acknowledging AI emotions)
        for i, ai_msg in enumerate(ai_messages):
            ai_lower = ai_msg.lower()
            
            # Check if AI expressed emotion
            ai_emotional = any(word in ai_lower for word in self.emotional_awareness_keywords)
            
            if ai_emotional and i + 1 < len(user_messages):
                # Check if user acknowledged in next response
                user_response = user_messages[i + 1].lower()
                if any(word in user_response for word in self.empathy_indicators):
                    tone_matching += 1
        
        # Calculate scores
        emotional_response_ratio = emotional_responses / len(ai_messages) if ai_messages else 0
        tone_matching_ratio = tone_matching / len(ai_messages) if ai_messages else 0
        
        emotional_awareness_score = (emotional_response_ratio * 50) + (tone_matching_ratio * 50)
        
        return min(emotional_awareness_score, 100.0)
    
    def _calculate_overall_eq_score(self, empathy: float, rapport: float, 
                                  adaptability: float, emotional_awareness: float) -> float:
        """Calculate overall emotional intelligence score"""
        # Weighted average
        weights = {
            'empathy': 0.3,      # 30% - Core EQ component
            'rapport': 0.25,     # 25% - Relationship building
            'adaptability': 0.25, # 25% - Flexibility and awareness
            'emotional_awareness': 0.2  # 20% - Emotional recognition
        }
        
        overall_score = (
            empathy * weights['empathy'] +
            rapport * weights['rapport'] +
            adaptability * weights['adaptability'] +
            emotional_awareness * weights['emotional_awareness']
        )
        
        return min(overall_score, 100.0)
    
    def _rate_emotional_intelligence(self, score: float) -> str:
        """Rate emotional intelligence level"""
        if score >= 80:
            return "exceptional"
        elif score >= 65:
            return "strong"
        elif score >= 50:
            return "adequate"
        elif score >= 35:
            return "developing"
        else:
            return "needs_significant_improvement"
    
    def _identify_eq_strengths_and_gaps(self, empathy: float, rapport: float, 
                                      adaptability: float, emotional_awareness: float) -> Tuple[List[str], List[str]]:
        """Identify EQ strengths and improvement areas"""
        strengths = []
        improvement_areas = []
        
        # Check each component
        if empathy >= 60:
            strengths.append("Strong empathetic responses")
        elif empathy < 30:
            improvement_areas.append("Show more empathy and understanding")
        
        if rapport >= 60:
            strengths.append("Excellent rapport building")
        elif rapport < 30:
            improvement_areas.append("Build stronger customer connections")
        
        if adaptability >= 60:
            strengths.append("Good adaptability to customer needs")
        elif adaptability < 30:
            improvement_areas.append("Adapt communication style to customer personality")
        
        if emotional_awareness >= 60:
            strengths.append("High emotional awareness")
        elif emotional_awareness < 30:
            improvement_areas.append("Better recognize and respond to customer emotions")
        
        return strengths, improvement_areas
    
    def get_eq_insights(self, analysis: EmotionalIntelligenceAnalysis) -> Dict[str, Any]:
        """Generate insights and recommendations from EQ analysis"""
        insights = {
            'eq_profile': f"Overall EQ Rating: {analysis.eq_rating}",
            'component_breakdown': {
                'empathy': f"{analysis.empathy_score:.1f}/100",
                'rapport': f"{analysis.rapport_score:.1f}/100",
                'adaptability': f"{analysis.adaptability_score:.1f}/100"
            },
            'strengths_count': len(analysis.strengths),
            'improvement_areas_count': len(analysis.improvement_areas),
            'recommendations': []
        }
        
        # Generate recommendations based on scores
        if analysis.empathy_score < 50:
            insights['recommendations'].append("Practice empathetic language like 'I understand your concern' or 'That makes sense'")
        
        if analysis.rapport_score < 50:
            insights['recommendations'].append("Use rapport-building phrases like 'That's interesting' or 'Tell me more'")
        
        if analysis.adaptability_score < 50:
            insights['recommendations'].append("Adapt your communication style to match the customer's personality and preferences")
        
        # Overall recommendations
        if analysis.overall_eq_score >= 70:
            insights['recommendations'].append("Continue developing strong emotional intelligence skills")
        elif analysis.overall_eq_score < 50:
            insights['recommendations'].append("Focus on building emotional awareness and empathy in customer interactions")
        
        return insights