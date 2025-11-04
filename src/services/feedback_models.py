"""
Feedback Service Models
Data structures and enums for the feedback analytics system
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
import time

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

class SalesPhase(Enum):
    """Sales process phases for analysis"""
    OPENING = "opening"
    DISCOVERY = "discovery"
    PRESENTATION = "presentation"
    HANDLING_OBJECTIONS = "handling_objections"
    CLOSING = "closing"
    FOLLOW_UP = "follow_up"

class CommunicationStyle(Enum):
    """Communication style classifications"""
    ASSERTIVE = "assertive"
    CONSULTATIVE = "consultative"
    RELATIONSHIP_FOCUSED = "relationship_focused"
    TASK_FOCUSED = "task_focused"
    PASSIVE = "passive"
    AGGRESSIVE = "aggressive"

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
        """Convert feedback item to dictionary format"""
        data = asdict(self)
        data['category'] = self.category.value
        data['feedback_type'] = self.feedback_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedbackItem':
        """Create feedback item from dictionary"""
        return cls(
            feedback_id=data['feedback_id'],
            category=FeedbackCategory(data['category']),
            feedback_type=FeedbackType(data['feedback_type']),
            title=data['title'],
            description=data['description'],
            specific_example=data['specific_example'],
            improvement_suggestion=data['improvement_suggestion'],
            confidence_score=data['confidence_score'],
            timestamp=data['timestamp']
        )

@dataclass
class ConversationMetrics:
    """Metrics extracted from conversation analysis"""
    total_turns: int
    user_turns: int
    ai_turns: int
    average_response_length: float
    total_duration: float
    conversation_flow_score: float
    engagement_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return asdict(self)

@dataclass
class CommunicationAnalysis:
    """Results of communication style analysis"""
    dominant_style: CommunicationStyle
    style_scores: Dict[str, float]
    question_analysis: Dict[str, Any]
    language_patterns: Dict[str, Any]
    effectiveness_rating: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis to dictionary"""
        data = asdict(self)
        data['dominant_style'] = self.dominant_style.value
        return data

@dataclass
class SalesProcessAnalysis:
    """Results of sales process analysis"""
    phases_covered: List[SalesPhase]
    phase_effectiveness: Dict[str, float]
    sales_techniques_used: List[str]
    process_score: float
    missing_phases: List[SalesPhase]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis to dictionary"""
        data = asdict(self)
        data['phases_covered'] = [phase.value for phase in self.phases_covered]
        data['missing_phases'] = [phase.value for phase in self.missing_phases]
        return data

@dataclass
class EmotionalIntelligenceAnalysis:
    """Results of emotional intelligence analysis"""
    empathy_score: float
    rapport_score: float
    adaptability_score: float
    overall_eq_score: float
    eq_rating: str
    strengths: List[str]
    improvement_areas: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis to dictionary"""
        return asdict(self)

@dataclass
class FeedbackSummary:
    """Complete feedback analysis summary"""
    session_id: str
    user_id: str
    timestamp: float
    conversation_metrics: ConversationMetrics
    communication_analysis: CommunicationAnalysis
    sales_process_analysis: SalesProcessAnalysis
    emotional_intelligence_analysis: EmotionalIntelligenceAnalysis
    feedback_items: List[FeedbackItem]
    overall_score: float
    overall_rating: str
    key_strengths: List[str]
    priority_improvements: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert complete summary to dictionary"""
        data = asdict(self)
        data['conversation_metrics'] = self.conversation_metrics.to_dict()
        data['communication_analysis'] = self.communication_analysis.to_dict()
        data['sales_process_analysis'] = self.sales_process_analysis.to_dict()
        data['emotional_intelligence_analysis'] = self.emotional_intelligence_analysis.to_dict()
        data['feedback_items'] = [item.to_dict() for item in self.feedback_items]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeedbackSummary':
        """Create feedback summary from dictionary"""
        return cls(
            session_id=data['session_id'],
            user_id=data['user_id'],
            timestamp=data['timestamp'],
            conversation_metrics=ConversationMetrics(**data['conversation_metrics']),
            communication_analysis=CommunicationAnalysis(
                dominant_style=CommunicationStyle(data['communication_analysis']['dominant_style']),
                **{k: v for k, v in data['communication_analysis'].items() if k != 'dominant_style'}
            ),
            sales_process_analysis=SalesProcessAnalysis(
                phases_covered=[SalesPhase(p) for p in data['sales_process_analysis']['phases_covered']],
                missing_phases=[SalesPhase(p) for p in data['sales_process_analysis']['missing_phases']],
                **{k: v for k, v in data['sales_process_analysis'].items() 
                   if k not in ['phases_covered', 'missing_phases']}
            ),
            emotional_intelligence_analysis=EmotionalIntelligenceAnalysis(**data['emotional_intelligence_analysis']),
            feedback_items=[FeedbackItem.from_dict(item) for item in data['feedback_items']],
            overall_score=data['overall_score'],
            overall_rating=data['overall_rating'],
            key_strengths=data['key_strengths'],
            priority_improvements=data['priority_improvements']
        )

# Utility functions for creating feedback items
def create_positive_feedback(category: FeedbackCategory, title: str, description: str, 
                           example: str, timestamp: float = None) -> FeedbackItem:
    """Create a positive feedback item"""
    return FeedbackItem(
        feedback_id=f"pos_{int(time.time() * 1000)}",
        category=category,
        feedback_type=FeedbackType.POSITIVE,
        title=title,
        description=description,
        specific_example=example,
        improvement_suggestion="Continue this excellent approach",
        confidence_score=0.9,
        timestamp=timestamp or time.time()
    )

def create_constructive_feedback(category: FeedbackCategory, title: str, description: str,
                               example: str, suggestion: str, confidence: float = 0.8,
                               timestamp: float = None) -> FeedbackItem:
    """Create constructive feedback item"""
    return FeedbackItem(
        feedback_id=f"const_{int(time.time() * 1000)}",
        category=category,
        feedback_type=FeedbackType.CONSTRUCTIVE,
        title=title,
        description=description,
        specific_example=example,
        improvement_suggestion=suggestion,
        confidence_score=confidence,
        timestamp=timestamp or time.time()
    )

def create_suggestion_feedback(category: FeedbackCategory, title: str, description: str,
                             suggestion: str, confidence: float = 0.7,
                             timestamp: float = None) -> FeedbackItem:
    """Create suggestion feedback item"""
    return FeedbackItem(
        feedback_id=f"sugg_{int(time.time() * 1000)}",
        category=category,
        feedback_type=FeedbackType.SUGGESTION,
        title=title,
        description=description,
        specific_example="",
        improvement_suggestion=suggestion,
        confidence_score=confidence,
        timestamp=timestamp or time.time()
    )