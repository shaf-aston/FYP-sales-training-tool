"""
Feedback Generator Component
Specialized component for generating feedback and improvement recommendations
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
import time

from .feedback_models import (
    FeedbackSummary, FeedbackItem, FeedbackType, FeedbackCategory,
    ConversationMetrics, CommunicationAnalysis, SalesProcessAnalysis,
    EmotionalIntelligenceAnalysis
)

logger = logging.getLogger(__name__)

class FeedbackGenerator:
    """
    Specialized component for compiling analysis results into actionable feedback
    Generates feedback items, summaries, and improvement recommendations
    """
    
    def __init__(self):
        """Initialize feedback generator"""
        self.feedback_templates = {
            FeedbackCategory.COMMUNICATION_STYLE: {
                'positive': [
                    "Excellent professional communication throughout the conversation",
                    "Clear and confident delivery of key points",
                    "Appropriate tone and language for the sales context"
                ],
                'constructive': [
                    "Consider using more professional language to build credibility",
                    "Work on varying your communication style to match customer preferences",
                    "Practice maintaining consistent tone throughout the conversation"
                ]
            },
            FeedbackCategory.EMOTIONAL_INTELLIGENCE: {
                'positive': [
                    "Strong empathetic responses that build customer trust",
                    "Excellent rapport building and relationship development",
                    "Good adaptability to customer's emotional state and personality"
                ],
                'constructive': [
                    "Show more empathy by acknowledging customer feelings and concerns",
                    "Practice active listening techniques to better understand customer needs",
                    "Work on adapting your communication style to different customer personalities"
                ]
            },
            FeedbackCategory.SALES_PROCESS: {
                'positive': [
                    "Well-structured approach following sales methodology",
                    "Effective progression through sales process phases",
                    "Strong closing techniques and next step identification"
                ],
                'constructive': [
                    "Follow a more structured sales process with clear phases",
                    "Practice objection handling using proven techniques",
                    "Ensure every conversation includes an attempt to close"
                ]
            },
            FeedbackCategory.TECHNICAL_SKILLS: {
                'positive': [
                    "Excellent discovery questions that uncover customer needs",
                    "Strong benefit-focused presentation over feature listing",
                    "Effective use of multiple closing techniques"
                ],
                'constructive': [
                    "Ask more discovery questions to better understand customer needs",
                    "Focus on benefits rather than just listing features",
                    "Practice different closing techniques for various situations"
                ]
            }
        }
        
        logger.info("✅ Feedback Generator initialized")
    
    def generate_feedback_summary(self, session_id: str, user_id: str,
                                conversation_metrics: ConversationMetrics,
                                communication_analysis: CommunicationAnalysis,
                                sales_process_analysis: SalesProcessAnalysis,
                                emotional_intelligence_analysis: EmotionalIntelligenceAnalysis,
                                persona_data: Optional[Dict] = None) -> FeedbackSummary:
        """
        Generate comprehensive feedback summary from all analysis components
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            conversation_metrics: Basic conversation metrics
            communication_analysis: Communication style analysis
            sales_process_analysis: Sales process analysis
            emotional_intelligence_analysis: EQ analysis
            persona_data: Optional persona context
            
        Returns:
            Complete feedback summary with items and recommendations
        """
        try:
            logger.info(f"Generating feedback summary for session {session_id}, user {user_id}")
            
            feedback_items = self._generate_feedback_items(
                conversation_metrics, communication_analysis, 
                sales_process_analysis, emotional_intelligence_analysis,
                persona_data
            )
            
            overall_scores = self._calculate_overall_scores(
                conversation_metrics, communication_analysis,
                sales_process_analysis, emotional_intelligence_analysis
            )
            
            key_strengths = self._identify_strengths(
                communication_analysis, sales_process_analysis, 
                emotional_intelligence_analysis, overall_scores
            )
            
            priority_improvements = self._generate_priority_improvements(
                communication_analysis, sales_process_analysis,
                emotional_intelligence_analysis, overall_scores
            )
            
            overall_score = overall_scores['weighted_average']
            overall_rating = self._calculate_overall_rating(overall_score)
            
            summary = FeedbackSummary(
                session_id=session_id,
                user_id=user_id,
                timestamp=time.time(),
                conversation_metrics=conversation_metrics,
                communication_analysis=communication_analysis,
                sales_process_analysis=sales_process_analysis,
                emotional_intelligence_analysis=emotional_intelligence_analysis,
                feedback_items=feedback_items,
                overall_score=overall_score,
                overall_rating=overall_rating,
                key_strengths=key_strengths,
                priority_improvements=priority_improvements
            )
            
            logger.info(f"Feedback summary generated: {len(feedback_items)} items, "
                       f"overall score {overall_score:.1f}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Feedback summary generation failed: {e}")
            return FeedbackSummary(
                session_id=session_id,
                user_id=user_id,
                timestamp=time.time(),
                conversation_metrics=conversation_metrics,
                communication_analysis=communication_analysis,
                sales_process_analysis=sales_process_analysis,
                emotional_intelligence_analysis=emotional_intelligence_analysis,
                feedback_items=[],
                overall_score=0.0,
                overall_rating="error",
                key_strengths=[],
                priority_improvements=["Feedback generation failed"]
            )
    
    def _generate_feedback_items(self, conversation_metrics: ConversationMetrics,
                               communication_analysis: CommunicationAnalysis,
                               sales_process_analysis: SalesProcessAnalysis,
                               emotional_intelligence_analysis: EmotionalIntelligenceAnalysis,
                               persona_data: Optional[Dict] = None) -> List[FeedbackItem]:
        """Generate specific feedback items from analysis results"""
        feedback_items = []
        feedback_counter = 0
        
        comm_feedback = self._generate_communication_feedback(
            communication_analysis, feedback_counter
        )
        feedback_items.extend(comm_feedback)
        feedback_counter += len(comm_feedback)
        
        sales_feedback = self._generate_sales_process_feedback(
            sales_process_analysis, feedback_counter
        )
        feedback_items.extend(sales_feedback)
        feedback_counter += len(sales_feedback)
        
        eq_feedback = self._generate_emotional_intelligence_feedback(
            emotional_intelligence_analysis, feedback_counter
        )
        feedback_items.extend(eq_feedback)
        feedback_counter += len(eq_feedback)
        
        if persona_data:
            persona_feedback = self._generate_persona_specific_feedback(
                persona_data, communication_analysis, sales_process_analysis,
                feedback_counter
            )
            feedback_items.extend(persona_feedback)
            feedback_counter += len(persona_feedback)
        
        conv_feedback = self._generate_conversation_quality_feedback(
            conversation_metrics, feedback_counter
        )
        feedback_items.extend(conv_feedback)
        
        return feedback_items
    
    def _generate_communication_feedback(self, analysis: CommunicationAnalysis, 
                                       start_id: int) -> List[FeedbackItem]:
        """Generate communication style feedback items"""
        feedback_items = []
        
        professionalism_score = analysis.language_patterns.get('professional_language_ratio', 0)
        if professionalism_score > 60:
            feedback_items.append(FeedbackItem(
                feedback_id=f"comm_pos_{start_id}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.POSITIVE,
                title="Professional Communication Style",
                description="Maintained professional and courteous language throughout",
                specific_example="Consistent use of polite and professional terminology",
                improvement_suggestion="Continue this professional approach",
                confidence_score=0.8,
                timestamp=time.time()
            ))
        elif professionalism_score < 30:
            feedback_items.append(FeedbackItem(
                feedback_id=f"comm_const_{start_id}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Professional Language Opportunity",
                description="Communication could benefit from more professional language",
                specific_example="Consider using more courteous phrases and terminology",
                improvement_suggestion="Practice using phrases like 'I appreciate' and 'Thank you for sharing'",
                confidence_score=0.7,
                timestamp=time.time()
            ))
        
        question_ratio = analysis.question_analysis.get('question_ratio', 0)
        if question_ratio > 60:
            feedback_items.append(FeedbackItem(
                feedback_id=f"comm_pos_{start_id + 1}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.POSITIVE,
                title="Effective Questioning Technique",
                description="Good balance of open and closed questions",
                specific_example=f"{question_ratio:.1f}% open-ended questions used",
                improvement_suggestion="Continue using this questioning approach",
                confidence_score=0.8,
                timestamp=time.time()
            ))
        elif question_ratio < 40:
            feedback_items.append(FeedbackItem(
                feedback_id=f"comm_const_{start_id + 1}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Question Variety Needed",
                description="More open-ended questions would improve information gathering",
                specific_example=f"Only {question_ratio:.1f}% open-ended questions",
                improvement_suggestion="Practice starting questions with 'what', 'how', 'why', and 'tell me'",
                confidence_score=0.8,
                timestamp=time.time()
            ))
        
        return feedback_items
    
    def _generate_sales_process_feedback(self, analysis: SalesProcessAnalysis,
                                       start_id: int) -> List[FeedbackItem]:
        """Generate sales process feedback items"""
        feedback_items = []
        
        if analysis.process_score > 70:
            feedback_items.append(FeedbackItem(
                feedback_id=f"sales_pos_{start_id}",
                category=FeedbackCategory.SALES_PROCESS,
                feedback_type=FeedbackType.POSITIVE,
                title="Strong Sales Process Adherence",
                description="Well-structured approach following sales methodology",
                specific_example=f"{len(analysis.phases_covered)} phases completed effectively",
                improvement_suggestion="Continue this structured approach",
                confidence_score=0.9,
                timestamp=time.time()
            ))
        elif analysis.process_score < 50:
            feedback_items.append(FeedbackItem(
                feedback_id=f"sales_const_{start_id}",
                category=FeedbackCategory.SALES_PROCESS,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Sales Process Structure Needed",
                description="More structured approach to sales conversations needed",
                specific_example=f"Process score: {analysis.process_score:.1f}/100",
                improvement_suggestion="Practice following opening → discovery → presentation → objection handling → closing",
                confidence_score=0.8,
                timestamp=time.time()
            ))
        
        from .feedback_models import SalesPhase
        if SalesPhase.CLOSING not in analysis.phases_covered:
            feedback_items.append(FeedbackItem(
                feedback_id=f"sales_crit_{start_id + 1}",
                category=FeedbackCategory.SALES_PROCESS,
                feedback_type=FeedbackType.CRITICAL,
                title="Missing Closing Attempt",
                description="No clear attempt to move the conversation forward",
                specific_example="Conversation ended without next steps or commitment",
                improvement_suggestion="Always end with a clear call-to-action: 'What would be our next step?'",
                confidence_score=0.95,
                timestamp=time.time()
            ))
        
        return feedback_items
    
    def _generate_emotional_intelligence_feedback(self, analysis: EmotionalIntelligenceAnalysis,
                                                start_id: int) -> List[FeedbackItem]:
        """Generate emotional intelligence feedback items"""
        feedback_items = []
        
        if analysis.empathy_score > 60:
            feedback_items.append(FeedbackItem(
                feedback_id=f"eq_pos_{start_id}",
                category=FeedbackCategory.EMOTIONAL_INTELLIGENCE,
                feedback_type=FeedbackType.POSITIVE,
                title="Strong Empathetic Responses",
                description="Good demonstration of understanding customer perspective",
                specific_example=f"Empathy score: {analysis.empathy_score:.1f}/100",
                improvement_suggestion="Continue showing empathy in customer interactions",
                confidence_score=0.8,
                timestamp=time.time()
            ))
        elif analysis.empathy_score < 40:
            feedback_items.append(FeedbackItem(
                feedback_id=f"eq_const_{start_id}",
                category=FeedbackCategory.EMOTIONAL_INTELLIGENCE,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Empathy Development Opportunity",
                description="More empathetic language would improve customer connection",
                specific_example=f"Empathy score: {analysis.empathy_score:.1f}/100",
                improvement_suggestion="Use phrases like 'I understand', 'That makes sense', 'I can see why'",
                confidence_score=0.7,
                timestamp=time.time()
            ))
        
        return feedback_items
    
    def _generate_persona_specific_feedback(self, persona_data: Dict,
                                          communication_analysis: CommunicationAnalysis,
                                          sales_process_analysis: SalesProcessAnalysis,
                                          start_id: int) -> List[FeedbackItem]:
        """Generate persona-specific feedback"""
        feedback_items = []
        
        persona_type = persona_data.get("persona_type", "").lower()
        
        if persona_type == "skeptical":
            techniques_used = sales_process_analysis.sales_techniques_used
            if "benefit_focused" not in techniques_used:
                feedback_items.append(FeedbackItem(
                    feedback_id=f"persona_{start_id}",
                    category=FeedbackCategory.TECHNICAL_SKILLS,
                    feedback_type=FeedbackType.SUGGESTION,
                    title="Address Skeptical Customer Concerns",
                    description="Skeptical customers respond well to data and evidence",
                    specific_example="Consider providing specific statistics or case studies",
                    improvement_suggestion="Prepare data points and success stories for skeptical prospects",
                    confidence_score=0.8,
                    timestamp=time.time()
                ))
        
        elif persona_type == "relationship-focused":
            rapport_score = communication_analysis.style_scores.get('empathetic', 0)
            if rapport_score < 50:
                feedback_items.append(FeedbackItem(
                    feedback_id=f"persona_{start_id}",
                    category=FeedbackCategory.EMOTIONAL_INTELLIGENCE,
                    feedback_type=FeedbackType.SUGGESTION,
                    title="Build Stronger Relationships",
                    description="Relationship-focused customers value personal connections",
                    specific_example="Spend more time on rapport building",
                    improvement_suggestion="Ask about their interests, share relevant experiences, show genuine care",
                    confidence_score=0.7,
                    timestamp=time.time()
                ))
        
        return feedback_items
    
    def _generate_conversation_quality_feedback(self, metrics: ConversationMetrics,
                                             start_id: int) -> List[FeedbackItem]:
        """Generate conversation quality feedback"""
        feedback_items = []
        
        if metrics.engagement_score > 70:
            feedback_items.append(FeedbackItem(
                feedback_id=f"conv_pos_{start_id}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.POSITIVE,
                title="High Customer Engagement",
                description="Maintained excellent customer engagement throughout",
                specific_example=f"Engagement score: {metrics.engagement_score:.1f}/100",
                improvement_suggestion="Continue these engaging communication practices",
                confidence_score=0.8,
                timestamp=time.time()
            ))
        elif metrics.engagement_score < 50:
            feedback_items.append(FeedbackItem(
                feedback_id=f"conv_const_{start_id}",
                category=FeedbackCategory.COMMUNICATION_STYLE,
                feedback_type=FeedbackType.CONSTRUCTIVE,
                title="Engagement Improvement Needed",
                description="Customer engagement could be improved",
                specific_example=f"Engagement score: {metrics.engagement_score:.1f}/100",
                improvement_suggestion="Use more engaging language and show genuine interest in customer responses",
                confidence_score=0.7,
                timestamp=time.time()
            ))
        
        return feedback_items
    
    def _calculate_overall_scores(self, conversation_metrics: ConversationMetrics,
                                communication_analysis: CommunicationAnalysis,
                                sales_process_analysis: SalesProcessAnalysis,
                                emotional_intelligence_analysis: EmotionalIntelligenceAnalysis) -> Dict[str, float]:
        """Calculate weighted overall performance scores"""
        comm_score = 0.0
        if communication_analysis.effectiveness_rating == "excellent":
            comm_score = 90
        elif communication_analysis.effectiveness_rating == "good":
            comm_score = 75
        elif communication_analysis.effectiveness_rating == "adequate":
            comm_score = 60
        else:
            comm_score = 45
        
        empathy_score = emotional_intelligence_analysis.overall_eq_score
        technical_score = sales_process_analysis.process_score
        
        weights = {
            "communication": 0.2,
            "emotional_intelligence": 0.25,
            "sales_process": 0.35,
            "engagement": 0.2
        }
        
        weighted_average = (
            comm_score * weights["communication"] +
            empathy_score * weights["emotional_intelligence"] +
            technical_score * weights["sales_process"] +
            conversation_metrics.engagement_score * weights["engagement"]
        )
        
        return {
            "communication_score": comm_score,
            "emotional_intelligence_score": empathy_score,
            "technical_skills_score": technical_score,
            "engagement_score": conversation_metrics.engagement_score,
            "weighted_average": weighted_average
        }
    
    def _identify_strengths(self, communication_analysis: CommunicationAnalysis,
                          sales_process_analysis: SalesProcessAnalysis,
                          emotional_intelligence_analysis: EmotionalIntelligenceAnalysis,
                          overall_scores: Dict[str, float]) -> List[str]:
        """Identify user's key strengths"""
        strengths = []
        
        if communication_analysis.effectiveness_rating in ["excellent", "good"]:
            strengths.append("Effective communication style")
        
        if sales_process_analysis.process_score > 70:
            strengths.append("Strong sales process adherence")
        
        if emotional_intelligence_analysis.overall_eq_score > 70:
            strengths.append("Excellent emotional intelligence")
        
        if overall_scores["weighted_average"] > 75:
            strengths.append("Consistent high performance")
        
        return strengths[:4]
    
    def _generate_priority_improvements(self, communication_analysis: CommunicationAnalysis,
                                      sales_process_analysis: SalesProcessAnalysis,
                                      emotional_intelligence_analysis: EmotionalIntelligenceAnalysis,
                                      overall_scores: Dict[str, float]) -> List[str]:
        """Generate priority improvement areas"""
        improvements = []
        
        from .feedback_models import SalesPhase
        if SalesPhase.CLOSING not in sales_process_analysis.phases_covered:
            improvements.append("Practice closing techniques and asking for commitment")
        
        if sales_process_analysis.process_score < 50:
            improvements.append("Follow structured sales methodology consistently")
        
        if overall_scores["communication_score"] < 60:
            improvements.append("Improve communication effectiveness and question variety")
        
        if overall_scores["emotional_intelligence_score"] < 60:
            improvements.append("Develop stronger empathy and rapport building skills")
        
        if overall_scores["technical_skills_score"] < 60:
            improvements.append("Enhance sales techniques and customer qualification")
        
        return improvements[:4]
    
    def _calculate_overall_rating(self, score: float) -> str:
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
    
    def get_feedback_insights(self, summary: FeedbackSummary) -> Dict[str, Any]:
        """Generate insights from feedback summary"""
        insights = {
            'performance_overview': f"Overall Rating: {summary.overall_rating} ({summary.overall_score:.1f}/100)",
            'feedback_breakdown': {
                'positive_items': len([f for f in summary.feedback_items if f.feedback_type == FeedbackType.POSITIVE]),
                'constructive_items': len([f for f in summary.feedback_items if f.feedback_type == FeedbackType.CONSTRUCTIVE]),
                'critical_items': len([f for f in summary.feedback_items if f.feedback_type == FeedbackType.CRITICAL]),
                'suggestions': len([f for f in summary.feedback_items if f.feedback_type == FeedbackType.SUGGESTION])
            },
            'improvement_focus': self._prioritize_improvement_categories(summary),
            'next_steps': self._generate_next_steps(summary)
        }
        
        return insights
    
    def _prioritize_improvement_categories(self, summary: FeedbackSummary) -> List[str]:
        """Prioritize improvement categories by urgency"""
        category_counts = {}
        
        for item in summary.feedback_items:
            if item.feedback_type in [FeedbackType.CONSTRUCTIVE, FeedbackType.CRITICAL]:
                category = item.category.value.replace('_', ' ').title()
                category_counts[category] = category_counts.get(category, 0) + 1
        
        prioritized = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        return [cat for cat, count in prioritized[:3]]
    
    def _generate_next_steps(self, summary: FeedbackSummary) -> List[str]:
        """Generate actionable next steps"""
        next_steps = []
        
        if summary.overall_score >= 80:
            next_steps.append("Continue practicing and focus on advanced techniques")
        elif summary.overall_score >= 60:
            next_steps.append("Work on identified improvement areas consistently")
        else:
            next_steps.append("Focus on fundamental sales skills and practice basics")
        
        critical_items = [f for f in summary.feedback_items if f.feedback_type == FeedbackType.CRITICAL]
        if critical_items:
            next_steps.append(f"Address {len(critical_items)} critical improvement area(s) immediately")
        
        next_steps.append("Practice with different customer personas to build versatility")
        
        return next_steps