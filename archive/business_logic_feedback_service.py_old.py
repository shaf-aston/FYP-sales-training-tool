"""
Feedback Analytics Service for AI Sales Training System
Analyzes conversations, provides feedback, and generates insights
"""
import json
import logging
import time
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from collections import Counter

from ..infrastructure.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

class FeedbackType(Enum):
    """Types of feedback categories"""
    POSITIVE = "positive"
    CONSTRUCTIVE = "constructive"
    CRITICAL = "critical"
    SUGGESTION = "suggestion"

class FeedbackCategory(Enum):
    """Categories for feedback classification"""
    COMMUNICATION_STYLE = "communication_style"
    TECHNICAL_SKILLS = "technical_skills"
    EMOTIONAL_INTELLIGENCE = "emotional_intelligence"
    SALES_PROCESS = "sales_process"
    PRODUCT_KNOWLEDGE = "product_knowledge"
    TIME_MANAGEMENT = "time_management"

@dataclass
class FeedbackItem:
    """Individual feedback item"""
    feedback_id: str
    category: FeedbackCategory
    feedback_type: FeedbackType
    title: str
    description: str
    specific_example: str
    improvement_suggestion: str
    confidence_score: float
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['category'] = self.category.value
        data['feedback_type'] = self.feedback_type.value
        return data

class FeedbackAnalyticsService:
    """Service for analyzing conversations and generating detailed feedback"""
    
    def __init__(self):
        self.feedback_patterns = self._initialize_feedback_patterns()
        self.session_analyses = {}
        self.user_feedback_history = {}
        self._initialize_nlp_components()
    
    def _initialize_nlp_components(self):
        """Initialize NLP components for text analysis"""
        # In production, this would initialize spaCy, NLTK, or similar
        # For now, using rule-based patterns
        
        self.sentiment_keywords = {
            "positive": ["great", "excellent", "perfect", "love", "amazing", "wonderful", "fantastic"],
            "negative": ["terrible", "awful", "hate", "worst", "horrible", "disgusting"],
            "neutral": ["okay", "fine", "alright", "decent", "acceptable"]
        }
        
        self.urgency_keywords = ["urgent", "immediately", "asap", "quickly", "rush", "emergency"]
        self.price_sensitivity_keywords = ["expensive", "cheap", "budget", "cost", "afford", "price", "money"]
        self.decision_keywords = ["decide", "think about", "consider", "discuss", "talk to", "spouse", "partner"]
    
    def _initialize_feedback_patterns(self) -> Dict[str, Any]:
        """Initialize patterns for feedback generation"""
        return {
            "rapport_building": {
                "good_indicators": [
                    "asked about personal interests",
                    "found common ground",
                    "used customer's name",
                    "showed genuine interest",
                    "built trust through conversation"
                ],
                "improvement_areas": [
                    "jumped into sales pitch too quickly",
                    "didn't ask enough personal questions",
                    "missed opportunities to connect",
                    "seemed too focused on features",
                    "didn't adapt communication style"
                ]
            },
            "objection_handling": {
                "good_indicators": [
                    "acknowledged the concern",
                    "asked clarifying questions",
                    "provided relevant evidence",
                    "turned objection into benefit",
                    "maintained positive tone"
                ],
                "improvement_areas": [
                    "became defensive",
                    "didn't address root cause",
                    "dismissed customer concerns",
                    "provided weak rebuttal",
                    "failed to confirm resolution"
                ]
            },
            "closing_techniques": {
                "good_indicators": [
                    "asked for the sale",
                    "created urgency appropriately",
                    "summarized benefits clearly",
                    "handled final objections",
                    "guided next steps"
                ],
                "improvement_areas": [
                    "didn't ask for commitment",
                    "weak closing attempt",
                    "created false urgency",
                    "pushed too hard",
                    "left conversation hanging"
                ]
            },
            "listening_skills": {
                "good_indicators": [
                    "referenced customer statements",
                    "asked follow-up questions",
                    "paraphrased to confirm understanding",
                    "picked up on emotional cues",
                    "tailored response to needs"
                ],
                "improvement_areas": [
                    "interrupted frequently",
                    "missed key information",
                    "didn't ask clarifying questions",
                    "ignored emotional signals",
                    "gave generic responses"
                ]
            }
        }
    
    def analyze_conversation(self, session_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Comprehensive conversation analysis with detailed feedback"""
        session_id = session_data.get("session_id", "unknown")
        conversation_history = session_data.get("conversation_history", [])
        persona_data = session_data.get("persona", {})
        
        if not conversation_history:
            return {"error": "No conversation data to analyze"}
        
        # Perform multi-level analysis
        analysis_results = {
            "session_id": session_id,
            "analysis_timestamp": time.time(),
            "conversation_metrics": self._analyze_conversation_metrics(conversation_history),
            "communication_analysis": self._analyze_communication_style(conversation_history),
            "sales_process_analysis": self._analyze_sales_process(conversation_history, persona_data),
            "emotional_intelligence": self._analyze_emotional_intelligence(conversation_history, persona_data),
            "technical_performance": self._analyze_technical_performance(conversation_history),
            "feedback_items": [],
            "overall_scores": {},
            "improvement_priorities": [],
            "strengths_identified": []
        }
        
        # Generate specific feedback items
        feedback_items = self._generate_feedback_items(analysis_results, conversation_history, persona_data)
        analysis_results["feedback_items"] = [item.to_dict() for item in feedback_items]
        
        # Calculate overall scores
        analysis_results["overall_scores"] = self._calculate_overall_scores(analysis_results)
        
        # Identify strengths and improvement areas
        analysis_results["strengths_identified"] = self._identify_strengths(analysis_results)
        analysis_results["improvement_priorities"] = self._prioritize_improvements(analysis_results)
        
        # Store analysis
        self.session_analyses[session_id] = analysis_results
        
        # Update user feedback history
        if user_id not in self.user_feedback_history:
            self.user_feedback_history[user_id] = []
        
        self.user_feedback_history[user_id].append({
            "session_id": session_id,
            "timestamp": time.time(),
            "overall_score": analysis_results["overall_scores"].get("weighted_average", 0),
            "key_feedback": [item for item in feedback_items if item.confidence_score > 0.7]
        })
        
        logger.info(f"Completed conversation analysis for session {session_id}")
        return analysis_results
    
    def _analyze_conversation_metrics(self, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Analyze basic conversation metrics"""
        if not conversation_history:
            return {}
        
        user_messages = [exchange.get("user_message", "") for exchange in conversation_history]
        persona_messages = [exchange.get("persona_response", "") for exchange in conversation_history]
        
        # Calculate message statistics
        user_word_counts = [len(msg.split()) for msg in user_messages]
        persona_word_counts = [len(msg.split()) for msg in persona_messages]
        
        # Calculate speaking ratios
        total_user_words = sum(user_word_counts)
        total_persona_words = sum(persona_word_counts)
        total_words = total_user_words + total_persona_words
        
        user_speaking_ratio = (total_user_words / total_words * 100) if total_words > 0 else 0
        
        # Analyze conversation flow
        conversation_turns = len(conversation_history)
        avg_user_message_length = sum(user_word_counts) / len(user_word_counts) if user_word_counts else 0
        avg_persona_message_length = sum(persona_word_counts) / len(persona_word_counts) if persona_word_counts else 0
        
        return {
            "total_exchanges": conversation_turns,
            "user_speaking_ratio": round(user_speaking_ratio, 1),
            "avg_user_message_length": round(avg_user_message_length, 1),
            "avg_persona_message_length": round(avg_persona_message_length, 1),
            "conversation_balance": "balanced" if 30 <= user_speaking_ratio <= 70 else "unbalanced",
            "total_words": total_words,
            "engagement_indicators": {
                "question_count": sum(1 for msg in user_messages if "?" in msg),
                "exclamation_count": sum(1 for msg in user_messages if "!" in msg),
                "conversation_depth": conversation_turns
            }
        }
    
    def _analyze_communication_style(self, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Analyze communication style and effectiveness"""
        user_messages = [exchange.get("user_message", "") for exchange in conversation_history]
        
        # Analyze tone and style
        professional_indicators = 0
        casual_indicators = 0
        empathetic_indicators = 0
        assertive_indicators = 0
        
        for message in user_messages:
            message_lower = message.lower()
            
            # Professional tone
            if any(word in message_lower for word in ["please", "thank you", "appreciate", "understand", "certainly"]):
                professional_indicators += 1
            
            # Casual tone
            if any(word in message_lower for word in ["yeah", "sure thing", "no worries", "awesome", "cool"]):
                casual_indicators += 1
            
            # Empathetic language
            if any(phrase in message_lower for phrase in ["i understand", "that makes sense", "i can see", "i hear you"]):
                empathetic_indicators += 1
            
            # Assertive language
            if any(word in message_lower for word in ["definitely", "absolutely", "confident", "guarantee", "ensure"]):
                assertive_indicators += 1
        
        # Calculate dominant style
        style_scores = {
            "professional": professional_indicators,
            "casual": casual_indicators,
            "empathetic": empathetic_indicators,
            "assertive": assertive_indicators
        }
        
        dominant_style = max(style_scores.items(), key=lambda x: x[1])[0]
        
        # Analyze question types
        open_questions = sum(1 for msg in user_messages if any(starter in msg.lower() for starter in ["what", "how", "why", "when", "where", "tell me"]))
        closed_questions = sum(1 for msg in user_messages if "?" in msg) - open_questions
        
        return {
            "dominant_style": dominant_style,
            "style_distribution": style_scores,
            "professionalism_score": min(100, professional_indicators * 20),
            "empathy_score": min(100, empathetic_indicators * 25),
            "assertiveness_score": min(100, assertive_indicators * 20),
            "question_analysis": {
                "open_questions": open_questions,
                "closed_questions": closed_questions,
                "question_ratio": round((open_questions / max(open_questions + closed_questions, 1)) * 100, 1)
            },
            "communication_effectiveness": self._rate_communication_effectiveness(style_scores, open_questions, closed_questions)
        }
    
    def _rate_communication_effectiveness(self, style_scores: Dict, open_questions: int, closed_questions: int) -> str:
        """Rate overall communication effectiveness"""
        total_style_points = sum(style_scores.values())
        question_balance = open_questions / max(open_questions + closed_questions, 1)
        
        if total_style_points >= 8 and question_balance > 0.6:
            return "excellent"
        elif total_style_points >= 5 and question_balance > 0.4:
            return "good"
        elif total_style_points >= 3:
            return "adequate"
        else:
            return "needs_improvement"
    
    def _analyze_sales_process(self, conversation_history: List[Dict], persona_data: Dict) -> Dict[str, Any]:
        """Analyze adherence to sales process and methodology"""
        user_messages = [exchange.get("user_message", "") for exchange in conversation_history]
        persona_messages = [exchange.get("persona_response", "") for exchange in conversation_history]
        
        # Track sales process stages
        stages_detected = {
            "opening": False,
            "rapport_building": False,
            "discovery": False,
            "presentation": False,
            "objection_handling": False,
            "closing": False,
            "follow_up": False
        }
        
        stage_transitions = []
        current_stage = "opening"
        
        for i, message in enumerate(user_messages):
            message_lower = message.lower()
            previous_stage = current_stage
            
            # Detect stage based on content
            if i == 0 or any(word in message_lower for word in ["hello", "hi", "good morning", "introduce"]):
                current_stage = "opening"
                stages_detected["opening"] = True
            elif any(phrase in message_lower for phrase in ["tell me about", "what do you", "how do you", "share with me"]):
                current_stage = "rapport_building"
                stages_detected["rapport_building"] = True
            elif any(word in message_lower for word in ["need", "looking for", "goal", "challenge", "problem"]):
                current_stage = "discovery"
                stages_detected["discovery"] = True
            elif any(word in message_lower for word in ["offer", "program", "feature", "benefit", "include"]):
                current_stage = "presentation"
                stages_detected["presentation"] = True
            elif any(word in message_lower for word in ["concern", "but", "however", "worry", "issue"]):
                current_stage = "objection_handling"
                stages_detected["objection_handling"] = True
            elif any(phrase in message_lower for phrase in ["ready to", "would you like", "shall we", "sign up", "get started"]):
                current_stage = "closing"
                stages_detected["closing"] = True
            elif any(word in message_lower for word in ["follow up", "next step", "contact", "schedule"]):
                current_stage = "follow_up"
                stages_detected["follow_up"] = True
            
            if current_stage != previous_stage:
                stage_transitions.append({
                    "from": previous_stage,
                    "to": current_stage,
                    "exchange": i + 1,
                    "message": message[:100] + "..." if len(message) > 100 else message
                })
        
        # Analyze objection handling specifically
        objections_raised = []
        objections_handled = []
        
        for i, persona_msg in enumerate(persona_messages):
            # Look for objections in persona responses
            persona_lower = persona_msg.lower()
            if any(word in persona_lower for word in ["but", "however", "concerned", "worried", "expensive", "not sure"]):
                objections_raised.append({
                    "exchange": i + 1,
                    "objection": persona_msg,
                    "handled": False
                })
                
                # Check if user handled it in next response
                if i + 1 < len(user_messages):
                    user_response = user_messages[i + 1].lower()
                    if any(phrase in user_response for phrase in ["understand", "appreciate", "let me", "what if", "consider"]):
                        objections_raised[-1]["handled"] = True
                        objections_handled.append(objections_raised[-1])
        
        # Calculate process adherence score
        stages_completed = sum(stages_detected.values())
        process_score = (stages_completed / len(stages_detected)) * 100
        
        return {
            "stages_completed": stages_detected,
            "process_adherence_score": round(process_score, 1),
            "stage_transitions": stage_transitions,
            "sales_methodology": {
                "followed_structure": stages_completed >= 4,
                "natural_flow": len(stage_transitions) <= len(user_messages) // 2,
                "comprehensive_discovery": stages_detected["discovery"],
                "effective_presentation": stages_detected["presentation"],
                "attempted_close": stages_detected["closing"]
            },
            "objection_handling": {
                "objections_raised": len(objections_raised),
                "objections_handled": len(objections_handled),
                "handling_success_rate": round((len(objections_handled) / max(len(objections_raised), 1)) * 100, 1),
                "objection_details": objections_raised
            }
        }
    
    def _analyze_emotional_intelligence(self, conversation_history: List[Dict], persona_data: Dict) -> Dict[str, Any]:
        """Analyze emotional intelligence and customer rapport"""
        user_messages = [exchange.get("user_message", "") for exchange in conversation_history]
        persona_messages = [exchange.get("persona_response", "") for exchange in conversation_history]
        
        # Analyze emotional awareness
        empathy_indicators = 0
        emotional_responses = 0
        tone_matching = 0
        
        for i, (user_msg, persona_msg) in enumerate(zip(user_messages, persona_messages)):
            user_lower = user_msg.lower()
            persona_lower = persona_msg.lower()
            
            # Check for empathy indicators
            if any(phrase in user_lower for phrase in ["i understand", "that must be", "i can see", "i hear you", "that makes sense"]):
                empathy_indicators += 1
            
            # Check for emotional responses
            if any(word in persona_lower for word in ["excited", "worried", "frustrated", "happy", "concerned", "thrilled"]):
                emotional_responses += 1
                
                # Check if user acknowledged emotion in next response
                if i + 1 < len(user_messages):
                    next_user = user_messages[i + 1].lower()
                    if any(word in next_user for word in ["understand", "appreciate", "see", "hear"]):
                        tone_matching += 1
        
        # Analyze persona-specific adaptation
        persona_traits = persona_data.get("personality_traits", [])
        persona_concerns = persona_data.get("concerns", [])
        
        adaptation_score = 0
        trait_acknowledgment = 0
        concern_addressing = 0
        
        all_user_text = " ".join(user_messages).lower()
        
        # Check if user adapted to persona traits
        for trait in persona_traits:
            trait_lower = trait.lower()
            if trait_lower == "cautious" and any(word in all_user_text for word in ["safe", "careful", "gradually", "step by step"]):
                trait_acknowledgment += 1
            elif trait_lower == "analytical" and any(word in all_user_text for word in ["data", "evidence", "research", "studies"]):
                trait_acknowledgment += 1
            elif trait_lower == "budget-conscious" and any(word in all_user_text for word in ["affordable", "value", "cost-effective", "budget"]):
                trait_acknowledgment += 1
        
        # Check if user addressed persona concerns
        for concern in persona_concerns:
            concern_lower = concern.lower()
            if any(word in concern_lower.split() for word in all_user_text.split()):
                concern_addressing += 1
        
        adaptation_score = ((trait_acknowledgment / max(len(persona_traits), 1)) + 
                          (concern_addressing / max(len(persona_concerns), 1))) * 50
        
        # Calculate emotional intelligence score
        ei_score = (
            (empathy_indicators * 15) +
            (tone_matching * 20) +
            (adaptation_score * 0.5)
        )
        
        return {
            "empathy_score": min(100, empathy_indicators * 25),
            "emotional_awareness": min(100, emotional_responses * 20),
            "tone_matching_score": min(100, tone_matching * 30),
            "persona_adaptation": {
                "adaptation_score": min(100, adaptation_score),
                "traits_acknowledged": trait_acknowledgment,
                "concerns_addressed": concern_addressing,
                "total_traits": len(persona_traits),
                "total_concerns": len(persona_concerns)
            },
            "overall_ei_score": min(100, ei_score),
            "ei_rating": self._rate_emotional_intelligence(ei_score)
        }
    
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
    
    def _analyze_technical_performance(self, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Analyze technical sales performance metrics"""
        user_messages = [exchange.get("user_message", "") for exchange in conversation_history]
        
        # Count technical elements
        questions_asked = sum(1 for msg in user_messages if "?" in msg)
        benefit_statements = sum(1 for msg in user_messages if any(word in msg.lower() for word in ["benefit", "help you", "advantage", "result"]))
        feature_mentions = sum(1 for msg in user_messages if any(word in msg.lower() for word in ["feature", "include", "offer", "provide"]))
        urgency_creation = sum(1 for msg in user_messages if any(word in msg.lower() for word in ["limited", "today", "now", "opportunity"]))
        closing_attempts = sum(1 for msg in user_messages if any(phrase in msg.lower() for phrase in ["ready to", "would you like", "shall we", "sign up"]))
        
        # Analyze conversation structure
        total_exchanges = len(conversation_history)
        discovery_ratio = questions_asked / max(total_exchanges, 1)
        presentation_ratio = (benefit_statements + feature_mentions) / max(total_exchanges, 1)
        
        # Technical performance score
        technical_score = (
            min(25, questions_asked * 5) +  # Discovery
            min(25, benefit_statements * 8) +  # Value presentation
            min(20, closing_attempts * 10) +  # Closing
            min(15, urgency_creation * 7) +  # Urgency
            min(15, feature_mentions * 3)  # Product knowledge
        )
        
        return {
            "discovery_metrics": {
                "questions_asked": questions_asked,
                "discovery_ratio": round(discovery_ratio * 100, 1),
                "discovery_rating": "excellent" if discovery_ratio > 0.4 else "good" if discovery_ratio > 0.2 else "needs_improvement"
            },
            "presentation_metrics": {
                "benefit_statements": benefit_statements,
                "feature_mentions": feature_mentions,
                "presentation_ratio": round(presentation_ratio * 100, 1),
                "value_focus": round((benefit_statements / max(benefit_statements + feature_mentions, 1)) * 100, 1)
            },
            "closing_metrics": {
                "closing_attempts": closing_attempts,
                "urgency_creation": urgency_creation,
                "closing_frequency": round(closing_attempts / max(total_exchanges, 1) * 100, 1)
            },
            "technical_performance_score": min(100, technical_score),
            "performance_rating": self._rate_technical_performance(technical_score)
        }
    
    def _rate_technical_performance(self, score: float) -> str:
        """Rate technical performance level"""
        if score >= 80:
            return "advanced"
        elif score >= 65:
            return "proficient"
        elif score >= 50:
            return "competent"
        elif score >= 35:
            return "developing"
        else:
            return "novice"
    
    def _generate_feedback_items(self, analysis_results: Dict, conversation_history: List[Dict], persona_data: Dict) -> List[FeedbackItem]:
        """Generate specific, actionable feedback items"""
        feedback_items = []
        feedback_counter = 0
        
        # Communication style feedback
        comm_analysis = analysis_results.get("communication_analysis", {})
        if comm_analysis.get("empathy_score", 0) < 50:
            feedback_items.append(FeedbackItem(
                feedback_id=f"feedback_{feedback_counter}",
                category=FeedbackCategory.EMOTIONAL_INTELLIGENCE,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Increase Empathetic Language",
                description="Your responses could show more understanding of the customer's perspective",
                specific_example="Try using phrases like 'I understand your concern' or 'That makes perfect sense'",
                improvement_suggestion="Practice acknowledging emotions before providing solutions",
                confidence_score=0.8,
                timestamp=time.time()
            ))
            feedback_counter += 1
        
        # Sales process feedback
        sales_analysis = analysis_results.get("sales_process_analysis", {})
        objection_handling = sales_analysis.get("objection_handling", {})
        
        if objection_handling.get("handling_success_rate", 0) < 70:
            feedback_items.append(FeedbackItem(
                feedback_id=f"feedback_{feedback_counter}",
                category=FeedbackCategory.TECHNICAL_SKILLS,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Improve Objection Handling",
                description="Several customer concerns were not fully addressed",
                specific_example=f"You handled {objection_handling.get('objections_handled', 0)} out of {objection_handling.get('objections_raised', 0)} objections",
                improvement_suggestion="Use the 'Feel, Felt, Found' method: 'I understand how you feel, others have felt the same way, and here's what they found...'",
                confidence_score=0.9,
                timestamp=time.time()
            ))
            feedback_counter += 1
        
        # Technical performance feedback
        tech_analysis = analysis_results.get("technical_performance", {})
        discovery_metrics = tech_analysis.get("discovery_metrics", {})
        
        if discovery_metrics.get("questions_asked", 0) < 3:
            feedback_items.append(FeedbackItem(
                feedback_id=f"feedback_{feedback_counter}",
                category=FeedbackCategory.SALES_PROCESS,
                feedback_type=FeedbackType.SUGGESTION,
                title="Ask More Discovery Questions",
                description="More questions will help you understand customer needs better",
                specific_example=f"You asked {discovery_metrics.get('questions_asked', 0)} questions in this conversation",
                improvement_suggestion="Try to ask 5-7 open-ended questions to fully understand their situation, goals, and challenges",
                confidence_score=0.85,
                timestamp=time.time()
            ))
            feedback_counter += 1
        
        # Closing feedback
        closing_metrics = tech_analysis.get("closing_metrics", {})
        if closing_metrics.get("closing_attempts", 0) == 0:
            feedback_items.append(FeedbackItem(
                feedback_id=f"feedback_{feedback_counter}",
                category=FeedbackCategory.SALES_PROCESS,
                feedback_type=FeedbackType.CRITICAL,
                title="Missing Closing Attempt",
                description="You didn't ask for the sale or commitment",
                specific_example="The conversation ended without a clear next step or commitment request",
                improvement_suggestion="Always end with a clear call to action: 'Are you ready to get started?' or 'What questions do you have about moving forward?'",
                confidence_score=0.95,
                timestamp=time.time()
            ))
            feedback_counter += 1
        
        # Positive feedback for strengths
        if comm_analysis.get("professionalism_score", 0) > 70:
            feedback_items.append(FeedbackItem(
                feedback_id=f"feedback_{feedback_counter}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.POSITIVE,
                title="Excellent Professional Tone",
                description="You maintained a professional and courteous tone throughout",
                specific_example="Your use of polite language and respectful communication was consistent",
                improvement_suggestion="Continue this professional approach while adding more personal connection",
                confidence_score=0.8,
                timestamp=time.time()
            ))
            feedback_counter += 1
        
        # Persona-specific feedback
        persona_type = persona_data.get("persona_type", "")
        if persona_type == "skeptical":
            # Look for data/proof usage
            user_messages = [exchange.get("user_message", "") for exchange in conversation_history]
            proof_usage = sum(1 for msg in user_messages if any(word in msg.lower() for word in ["study", "research", "data", "proven", "evidence"]))
            
            if proof_usage == 0:
                feedback_items.append(FeedbackItem(
                    feedback_id=f"feedback_{feedback_counter}",
                    category=FeedbackCategory.TECHNICAL_SKILLS,
                    feedback_type=FeedbackType.SUGGESTION,
                    title="Use More Proof Points with Skeptical Customers",
                    description="This customer type responds well to data and evidence",
                    specific_example="You didn't provide any studies, testimonials, or concrete evidence",
                    improvement_suggestion="Prepare specific statistics, case studies, and testimonials for skeptical prospects",
                    confidence_score=0.9,
                    timestamp=time.time()
                ))
                feedback_counter += 1
        
        return feedback_items
    
    def _calculate_overall_scores(self, analysis_results: Dict) -> Dict[str, float]:
        """Calculate weighted overall performance scores"""
        # Extract individual scores
        comm_score = analysis_results.get("communication_analysis", {}).get("professionalism_score", 0)
        empathy_score = analysis_results.get("emotional_intelligence", {}).get("overall_ei_score", 0)
        technical_score = analysis_results.get("technical_performance", {}).get("technical_performance_score", 0)
        process_score = analysis_results.get("sales_process_analysis", {}).get("process_adherence_score", 0)
        
        # Weighted average (adjust weights based on importance)
        weights = {
            "communication": 0.2,
            "emotional_intelligence": 0.25,
            "technical_skills": 0.3,
            "sales_process": 0.25
        }
        
        weighted_average = (
            comm_score * weights["communication"] +
            empathy_score * weights["emotional_intelligence"] +
            technical_score * weights["technical_skills"] +
            process_score * weights["sales_process"]
        )
        
        return {
            "communication_score": round(comm_score, 1),
            "emotional_intelligence_score": round(empathy_score, 1),
            "technical_skills_score": round(technical_score, 1),
            "sales_process_score": round(process_score, 1),
            "weighted_average": round(weighted_average, 1),
            "performance_grade": self._calculate_grade(weighted_average)
        }
    
    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade based on score"""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        else:
            return "F"
    
    def _identify_strengths(self, analysis_results: Dict) -> List[str]:
        """Identify user's key strengths from the analysis"""
        strengths = []
        
        # Check communication strengths
        comm_analysis = analysis_results.get("communication_analysis", {})
        if comm_analysis.get("professionalism_score", 0) > 70:
            strengths.append("Professional communication style")
        if comm_analysis.get("empathy_score", 0) > 70:
            strengths.append("Empathetic responses")
        
        # Check emotional intelligence strengths
        ei_analysis = analysis_results.get("emotional_intelligence", {})
        if ei_analysis.get("persona_adaptation", {}).get("adaptation_score", 0) > 70:
            strengths.append("Good persona adaptation")
        if ei_analysis.get("tone_matching_score", 0) > 70:
            strengths.append("Effective tone matching")
        
        # Check technical strengths
        tech_analysis = analysis_results.get("technical_performance", {})
        if tech_analysis.get("discovery_metrics", {}).get("questions_asked", 0) >= 5:
            strengths.append("Thorough discovery process")
        if tech_analysis.get("presentation_metrics", {}).get("benefit_statements", 0) >= 3:
            strengths.append("Strong benefit presentation")
        
        # Check sales process strengths
        sales_analysis = analysis_results.get("sales_process_analysis", {})
        if sales_analysis.get("objection_handling", {}).get("handling_success_rate", 0) > 80:
            strengths.append("Excellent objection handling")
        if sales_analysis.get("process_adherence_score", 0) > 75:
            strengths.append("Good sales process adherence")
        
        return strengths
    
    def _prioritize_improvements(self, analysis_results: Dict) -> List[Dict[str, Any]]:
        """Prioritize improvement areas by impact and urgency"""
        improvements = []
        
        # Analyze gaps and create priority improvements
        scores = analysis_results.get("overall_scores", {})
        
        improvement_areas = [
            {
                "area": "Sales Process",
                "current_score": scores.get("sales_process_score", 0),
                "impact": "high",
                "urgency": "high" if scores.get("sales_process_score", 0) < 60 else "medium"
            },
            {
                "area": "Technical Skills",
                "current_score": scores.get("technical_skills_score", 0),
                "impact": "high",
                "urgency": "high" if scores.get("technical_skills_score", 0) < 50 else "medium"
            },
            {
                "area": "Emotional Intelligence",
                "current_score": scores.get("emotional_intelligence_score", 0),
                "impact": "medium",
                "urgency": "medium" if scores.get("emotional_intelligence_score", 0) < 60 else "low"
            },
            {
                "area": "Communication Style",
                "current_score": scores.get("communication_score", 0),
                "impact": "medium",
                "urgency": "low" if scores.get("communication_score", 0) > 60 else "medium"
            }
        ]
        
        # Sort by urgency and impact
        priority_weights = {"high": 3, "medium": 2, "low": 1}
        
        for area in improvement_areas:
            priority_score = priority_weights[area["urgency"]] * 2 + priority_weights[area["impact"]]
            area["priority_score"] = priority_score
            
            # Add specific recommendations
            if area["area"] == "Sales Process" and area["current_score"] < 60:
                area["recommendations"] = [
                    "Practice structured sales methodology",
                    "Focus on closing techniques",
                    "Improve objection handling skills"
                ]
            elif area["area"] == "Technical Skills" and area["current_score"] < 50:
                area["recommendations"] = [
                    "Ask more discovery questions",
                    "Present more benefits vs features",
                    "Practice multiple closing techniques"
                ]
            elif area["area"] == "Emotional Intelligence" and area["current_score"] < 60:
                area["recommendations"] = [
                    "Practice active listening",
                    "Improve empathetic responses",
                    "Better adapt to customer personality"
                ]
            elif area["area"] == "Communication Style" and area["current_score"] < 60:
                area["recommendations"] = [
                    "Use more professional language",
                    "Balance speaking vs listening time",
                    "Improve question asking techniques"
                ]
        
        # Sort by priority score (highest first)
        improvements = sorted(improvement_areas, key=lambda x: x["priority_score"], reverse=True)
        
        return improvements[:3]  # Return top 3 priorities
    
    def generate_improvement_plan(self, user_id: str, timeframe_days: int = 30) -> Dict[str, Any]:
        """Generate a personalized improvement plan based on recent feedback"""
        if user_id not in self.user_feedback_history:
            return {"error": "No feedback history found for user"}
        
        recent_feedback = self.user_feedback_history[user_id][-5:]  # Last 5 sessions
        
        # Analyze patterns in feedback
        common_issues = {}
        improvement_trends = {}
        
        for session_feedback in recent_feedback:
            for feedback_item in session_feedback.get("key_feedback", []):
                category = feedback_item.category
                if category not in common_issues:
                    common_issues[category] = 0
                common_issues[category] += 1
        
        # Create structured improvement plan
        plan = {
            "user_id": user_id,
            "plan_created": time.time(),
            "timeframe_days": timeframe_days,
            "current_level": self._assess_current_level(recent_feedback),
            "focus_areas": self._identify_focus_areas(common_issues),
            "weekly_goals": self._create_weekly_goals(common_issues, timeframe_days),
            "recommended_scenarios": self._recommend_training_scenarios(common_issues),
            "success_metrics": self._define_success_metrics(common_issues),
            "resources": self._suggest_learning_resources(common_issues)
        }
        
        return plan
    
    def _assess_current_level(self, recent_feedback: List[Dict]) -> str:
        """Assess user's current overall skill level"""
        if not recent_feedback:
            return "beginner"
        
        avg_score = sum(session["overall_score"] for session in recent_feedback) / len(recent_feedback)
        
        if avg_score >= 85:
            return "advanced"
        elif avg_score >= 70:
            return "intermediate"
        elif avg_score >= 55:
            return "developing"
        else:
            return "beginner"
    
    def _identify_focus_areas(self, common_issues: Dict) -> List[str]:
        """Identify top focus areas based on feedback patterns"""
        # Sort issues by frequency
        sorted_issues = sorted(common_issues.items(), key=lambda x: x[1], reverse=True)
        
        # Convert to readable focus areas
        focus_areas = []
        for category, count in sorted_issues[:3]:  # Top 3 issues
            if category == FeedbackCategory.TECHNICAL_SKILLS:
                focus_areas.append("Technical Sales Skills")
            elif category == FeedbackCategory.EMOTIONAL_INTELLIGENCE:
                focus_areas.append("Customer Rapport & Empathy")
            elif category == FeedbackCategory.SALES_PROCESS:
                focus_areas.append("Sales Process & Methodology")
            elif category == FeedbackCategory.COMMUNICATION_STYLE:
                focus_areas.append("Communication Effectiveness")
        
        return focus_areas
    
    def _create_weekly_goals(self, common_issues: Dict, timeframe_days: int) -> List[Dict[str, Any]]:
        """Create weekly goals for the improvement plan"""
        weeks = min(4, timeframe_days // 7)  # Max 4 weeks of goals
        weekly_goals = []
        
        focus_categories = sorted(common_issues.items(), key=lambda x: x[1], reverse=True)
        
        for week in range(weeks):
            if week < len(focus_categories):
                category = focus_categories[week][0]
                goals = self._get_category_goals(category, week + 1)
            else:
                goals = ["Practice advanced scenarios", "Refine existing skills"]
            
            weekly_goals.append({
                "week": week + 1,
                "focus_theme": self._get_week_theme(category if week < len(focus_categories) else None, week + 1),
                "specific_goals": goals,
                "target_sessions": 3 + week,  # Gradually increase sessions
                "success_criteria": f"Achieve {70 + week * 5}% average score in focus area"
            })
        
        return weekly_goals
    
    def _get_category_goals(self, category: FeedbackCategory, week: int) -> List[str]:
        """Get specific goals for a feedback category"""
        goals_map = {
            FeedbackCategory.TECHNICAL_SKILLS: [
                "Practice asking 5+ discovery questions per session",
                "Focus on benefit statements over feature mentions",
                "Attempt to close in every conversation"
            ],
            FeedbackCategory.EMOTIONAL_INTELLIGENCE: [
                "Use empathetic language in every response",
                "Practice active listening techniques",
                "Adapt communication style to persona type"
            ],
            FeedbackCategory.SALES_PROCESS: [
                "Follow structured sales methodology",
                "Handle objections using Feel-Felt-Found technique",
                "Complete all sales process stages"
            ],
            FeedbackCategory.COMMUNICATION_STYLE: [
                "Maintain professional tone throughout",
                "Balance talking vs listening time",
                "Use customer's name frequently"
            ]
        }
        
        return goals_map.get(category, ["General skill improvement"])
    
    def _get_week_theme(self, category: Optional[FeedbackCategory], week: int) -> str:
        """Get theme for the week based on category"""
        if not category:
            return f"Week {week}: Advanced Practice"
        
        themes = {
            FeedbackCategory.TECHNICAL_SKILLS: f"Week {week}: Technical Sales Mastery",
            FeedbackCategory.EMOTIONAL_INTELLIGENCE: f"Week {week}: Customer Connection",
            FeedbackCategory.SALES_PROCESS: f"Week {week}: Process Excellence",
            FeedbackCategory.COMMUNICATION_STYLE: f"Week {week}: Communication Mastery"
        }
        
        return themes.get(category, f"Week {week}: General Improvement")
    
    def _recommend_training_scenarios(self, common_issues: Dict) -> List[Dict[str, Any]]:
        """Recommend specific training scenarios based on improvement needs"""
        scenarios = []
        
        for category, frequency in common_issues.items():
            if category == FeedbackCategory.TECHNICAL_SKILLS:
                scenarios.append({
                    "scenario_type": "Technical Skills Practice",
                    "recommended_personas": ["skeptical", "analytical"],
                    "focus_areas": ["questioning techniques", "benefit presentation", "closing"],
                    "difficulty": "medium_to_hard",
                    "sessions_recommended": max(3, frequency)
                })
            elif category == FeedbackCategory.EMOTIONAL_INTELLIGENCE:
                scenarios.append({
                    "scenario_type": "Rapport Building Practice",
                    "recommended_personas": ["worried", "emotional", "relationship-focused"],
                    "focus_areas": ["empathy", "active listening", "emotional responses"],
                    "difficulty": "easy_to_medium",
                    "sessions_recommended": max(2, frequency)
                })
        
        return scenarios
    
    def _define_success_metrics(self, common_issues: Dict) -> Dict[str, Any]:
        """Define success metrics for the improvement plan"""
        return {
            "target_overall_score": 75,
            "minimum_sessions_per_week": 3,
            "target_improvement_areas": len(common_issues),
            "success_indicators": [
                "Consistent scores above 70% in all categories",
                "Successful objection handling in 80% of sessions",
                "At least 3 closing attempts per session",
                "Positive feedback on empathy and rapport building"
            ]
        }
    
    def _suggest_learning_resources(self, common_issues: Dict) -> List[Dict[str, Any]]:
        """Suggest learning resources based on improvement areas"""
        resources = []
        
        resource_map = {
            FeedbackCategory.TECHNICAL_SKILLS: {
                "title": "Advanced Sales Techniques",
                "type": "training_module",
                "description": "Master discovery questions, benefit presentation, and closing techniques",
                "estimated_time": "2-3 hours"
            },
            FeedbackCategory.EMOTIONAL_INTELLIGENCE: {
                "title": "Customer Psychology & Rapport Building",
                "type": "training_module", 
                "description": "Learn to read customer emotions and build authentic connections",
                "estimated_time": "1-2 hours"
            },
            FeedbackCategory.SALES_PROCESS: {
                "title": "Sales Methodology Mastery",
                "type": "training_module",
                "description": "Structured approach to sales conversations and objection handling",
                "estimated_time": "2-3 hours"
            },
            FeedbackCategory.COMMUNICATION_STYLE: {
                "title": "Professional Communication Skills",
                "type": "training_module",
                "description": "Improve verbal and non-verbal communication effectiveness",
                "estimated_time": "1-2 hours"
            }
        }
        
        for category in common_issues.keys():
            if category in resource_map:
                resources.append(resource_map[category])
        
        return resources
    
    def get_analytics_dashboard(self, user_id: str = None, timeframe_days: int = 30) -> Dict[str, Any]:
        """Generate analytics dashboard for user or system-wide metrics"""
        cutoff_time = time.time() - (timeframe_days * 24 * 3600)
        
        if user_id:
            # User-specific dashboard
            if user_id not in self.user_feedback_history:
                return {"error": "User not found"}
            
            user_sessions = [s for s in self.user_feedback_history[user_id] if s["timestamp"] > cutoff_time]
            
            return {
                "user_id": user_id,
                "timeframe_days": timeframe_days,
                "total_sessions": len(user_sessions),
                "average_score": sum(s["overall_score"] for s in user_sessions) / max(len(user_sessions), 1),
                "score_trend": self._calculate_score_trend(user_sessions),
                "improvement_rate": self._calculate_improvement_rate(user_sessions),
                "category_breakdown": self._analyze_category_performance(user_sessions),
                "recent_achievements": self._get_recent_achievements(user_id, cutoff_time)
            }
        else:
            # System-wide dashboard
            total_sessions = len(self.session_analyses)
            all_scores = [analysis["overall_scores"]["weighted_average"] 
                         for analysis in self.session_analyses.values() 
                         if analysis.get("analysis_timestamp", 0) > cutoff_time]
            
            return {
                "system_metrics": {
                    "total_sessions_analyzed": total_sessions,
                    "sessions_in_timeframe": len(all_scores),
                    "average_system_score": sum(all_scores) / max(len(all_scores), 1),
                    "active_users": len(self.user_feedback_history),
                    "total_feedback_items": sum(len(analysis["feedback_items"]) for analysis in self.session_analyses.values())
                },
                "performance_distribution": self._analyze_score_distribution(all_scores),
                "common_improvement_areas": self._identify_system_improvement_areas(),
                "success_rate_by_category": self._calculate_category_success_rates()
            }
    
    def _calculate_score_trend(self, sessions: List[Dict]) -> str:
        """Calculate score trend over recent sessions"""
        if len(sessions) < 3:
            return "insufficient_data"
        
        recent_avg = sum(s["overall_score"] for s in sessions[-3:]) / 3
        older_avg = sum(s["overall_score"] for s in sessions[:-3]) / max(len(sessions) - 3, 1)
        
        if recent_avg > older_avg + 5:
            return "improving"
        elif recent_avg < older_avg - 5:
            return "declining"
        else:
            return "stable"
    
    def _calculate_improvement_rate(self, sessions: List[Dict]) -> float:
        """Calculate rate of improvement per session"""
        if len(sessions) < 2:
            return 0.0
        
        first_score = sessions[0]["overall_score"]
        last_score = sessions[-1]["overall_score"]
        
        return (last_score - first_score) / len(sessions)

# Global feedback analytics service instance
feedback_service = FeedbackAnalyticsService()