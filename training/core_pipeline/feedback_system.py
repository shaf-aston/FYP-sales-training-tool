"""
Feedback System Implementation
Performance classifiers and suggestion generators for sales training improvement
"""
import json
import numpy as np
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd
import re

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    """Sales performance metrics"""
    conversation_score: float
    technique_usage: Dict[str, float]
    objection_handling: float
    closing_effectiveness: float
    rapport_building: float
    needs_discovery: float
    value_presentation: float
    overall_rating: str  # 'excellent', 'good', 'needs_improvement', 'poor'

@dataclass
class FeedbackSuggestion:
    """Individual feedback suggestion"""
    category: str
    priority: str  # 'high', 'medium', 'low'
    message: str
    specific_examples: List[str]
    improvement_tips: List[str]

class SalesPerformanceClassifier:
    """Classifies sales conversation performance across multiple dimensions"""
    
    def __init__(self):
        self.classifiers = {}
        self.vectorizers = {}
        self.sales_techniques = self._define_sales_techniques()
        self.performance_indicators = self._define_performance_indicators()
        
    def _define_sales_techniques(self) -> Dict[str, List[str]]:
        """Define sales techniques and their indicators"""
        return {
            'rapport_building': [
                'great to meet you', 'thanks for your time', 'i appreciate',
                'understand your situation', 'similar to', 'i can relate'
            ],
            'needs_discovery': [
                'tell me about', 'what\'s important', 'how do you currently',
                'what challenges', 'what would you like', 'help me understand'
            ],
            'value_presentation': [
                'this means', 'the benefit is', 'you\'ll save', 'this helps you',
                'return on investment', 'value proposition', 'impact on your business'
            ],
            'objection_handling': [
                'i understand your concern', 'many clients felt the same',
                'that\'s a great question', 'let me address that', 'fair point'
            ],
            'closing_techniques': [
                'what would you like to do next', 'shall we move forward',
                'ready to get started', 'next steps', 'when can we begin'
            ]
        }
    
    def _define_performance_indicators(self) -> Dict[str, Dict]:
        """Define performance indicators for classification"""
        return {
            'excellent': {
                'technique_diversity': 0.8,  # Uses multiple techniques
                'objection_response_rate': 0.9,  # Addresses objections well
                'closing_attempts': 1.0,  # Makes appropriate closing attempts
                'rapport_indicators': 0.7,  # Good rapport building
                'value_focus': 0.8  # Focuses on value/benefits
            },
            'good': {
                'technique_diversity': 0.6,
                'objection_response_rate': 0.7,
                'closing_attempts': 0.7,
                'rapport_indicators': 0.5,
                'value_focus': 0.6
            },
            'needs_improvement': {
                'technique_diversity': 0.4,
                'objection_response_rate': 0.5,
                'closing_attempts': 0.4,
                'rapport_indicators': 0.3,
                'value_focus': 0.4
            }
        }
    
    def analyze_conversation(self, conversation_text: str, user_responses: List[str]) -> PerformanceMetrics:
        """Analyze sales conversation performance"""
        
        # Combine all user responses
        user_text = ' '.join(user_responses).lower()
        
        # Analyze technique usage
        technique_scores = {}
        for technique, indicators in self.sales_techniques.items():
            score = sum(1 for indicator in indicators if indicator in user_text)
            technique_scores[technique] = min(score / len(indicators), 1.0)
        
        # Calculate specific performance metrics
        objection_handling = self._evaluate_objection_handling(conversation_text, user_responses)
        closing_effectiveness = self._evaluate_closing_effectiveness(user_responses)
        overall_score = self._calculate_overall_score(technique_scores, objection_handling, closing_effectiveness)
        
        # Determine overall rating
        overall_rating = self._determine_rating(overall_score, technique_scores)
        
        return PerformanceMetrics(
            conversation_score=overall_score,
            technique_usage=technique_scores,
            objection_handling=objection_handling,
            closing_effectiveness=closing_effectiveness,
            rapport_building=technique_scores.get('rapport_building', 0.0),
            needs_discovery=technique_scores.get('needs_discovery', 0.0),
            value_presentation=technique_scores.get('value_presentation', 0.0),
            overall_rating=overall_rating
        )
    
    def _evaluate_objection_handling(self, conversation: str, user_responses: List[str]) -> float:
        """Evaluate how well objections were handled"""
        objection_keywords = ['but', 'however', 'concern', 'worried', 'expensive', 'not sure']
        
        # Find objections in conversation
        objections_raised = 0
        objections_addressed = 0
        
        conversation_lower = conversation.lower()
        for keyword in objection_keywords:
            if keyword in conversation_lower:
                objections_raised += 1
                
                # Check if user responded to objection
                for response in user_responses:
                    if any(phrase in response.lower() for phrase in self.sales_techniques['objection_handling']):
                        objections_addressed += 1
                        break
        
        if objections_raised == 0:
            return 0.5  # No objections to handle
        
        return objections_addressed / objections_raised
    
    def _evaluate_closing_effectiveness(self, user_responses: List[str]) -> float:
        """Evaluate closing effectiveness"""
        closing_attempts = 0
        total_responses = len(user_responses)
        
        if total_responses == 0:
            return 0.0
        
        for response in user_responses:
            response_lower = response.lower()
            if any(phrase in response_lower for phrase in self.sales_techniques['closing_techniques']):
                closing_attempts += 1
        
        # Expect at least one closing attempt in longer conversations
        expected_closes = max(1, total_responses // 5)
        return min(closing_attempts / expected_closes, 1.0)
    
    def _calculate_overall_score(self, technique_scores: Dict, objection_handling: float, closing_effectiveness: float) -> float:
        """Calculate overall conversation score"""
        technique_avg = np.mean(list(technique_scores.values())) if technique_scores else 0.0
        
        # Weighted average
        weights = {
            'techniques': 0.4,
            'objections': 0.3,
            'closing': 0.3
        }
        
        overall_score = (
            technique_avg * weights['techniques'] +
            objection_handling * weights['objections'] +
            closing_effectiveness * weights['closing']
        )
        
        return min(overall_score, 1.0)
    
    def _determine_rating(self, overall_score: float, technique_scores: Dict) -> str:
        """Determine overall performance rating"""
        if overall_score >= 0.8 and np.mean(list(technique_scores.values())) >= 0.7:
            return 'excellent'
        elif overall_score >= 0.6:
            return 'good'
        elif overall_score >= 0.4:
            return 'needs_improvement'
        else:
            return 'poor'

class FeedbackGenerator:
    """Generates specific, actionable feedback for sales improvement"""
    
    def __init__(self):
        self.feedback_templates = self._load_feedback_templates()
        
    def _load_feedback_templates(self) -> Dict[str, Dict]:
        """Load feedback message templates"""
        return {
            'rapport_building': {
                'low': {
                    'message': "Focus on building better rapport with prospects",
                    'tips': [
                        "Start conversations with genuine interest in their business",
                        "Use phrases like 'I understand' and 'That makes sense'",
                        "Find common ground or shared experiences",
                        "Ask about their role and responsibilities"
                    ]
                },
                'medium': {
                    'message': "Good rapport building, but could be more consistent",
                    'tips': [
                        "Continue using empathetic language",
                        "Ask more personal business questions",
                        "Reference previous conversation points"
                    ]
                }
            },
            'needs_discovery': {
                'low': {
                    'message': "Spend more time understanding prospect needs",
                    'tips': [
                        "Ask open-ended questions about current processes",
                        "Probe deeper into pain points and challenges",
                        "Use 'Tell me more about...' to gather information",
                        "Listen more than you talk in the early stages"
                    ]
                },
                'medium': {
                    'message': "Good questioning technique, but dig deeper",
                    'tips': [
                        "Follow up with 'What does that mean for your business?'",
                        "Ask about the impact of current challenges",
                        "Explore budget and decision-making processes"
                    ]
                }
            },
            'value_presentation': {
                'low': {
                    'message': "Better connect features to specific benefits",
                    'tips': [
                        "Use 'This means...' or 'The benefit to you is...'",
                        "Quantify value with numbers when possible",
                        "Connect benefits to their stated needs",
                        "Focus on business impact, not just features"
                    ]
                },
                'medium': {
                    'message': "Good value presentation, make it more specific",
                    'tips': [
                        "Use their company name and specific situation",
                        "Reference exact numbers from their challenges",
                        "Paint a picture of their improved future state"
                    ]
                }
            },
            'objection_handling': {
                'low': {
                    'message': "Improve objection handling techniques",
                    'tips': [
                        "Acknowledge objections before responding",
                        "Use 'I understand your concern about...'",
                        "Ask clarifying questions about objections",
                        "Provide specific examples or proof points"
                    ]
                },
                'medium': {
                    'message': "Decent objection handling, be more proactive",
                    'tips': [
                        "Anticipate common objections early",
                        "Use testimonials and case studies",
                        "Address root causes, not just symptoms"
                    ]
                }
            },
            'closing_techniques': {
                'low': {
                    'message': "Be more proactive about moving the sale forward",
                    'tips': [
                        "Ask for next steps at the end of calls",
                        "Use assumptive language: 'When we implement this...'",
                        "Create urgency with timeline or limited availability",
                        "Ask direct questions: 'What would you like to do next?'"
                    ]
                },
                'medium': {
                    'message': "Good closing attempts, try different approaches",
                    'tips': [
                        "Use alternative choice closes",
                        "Trial close throughout the conversation",
                        "Address any remaining concerns before closing"
                    ]
                }
            }
        }
    
    def generate_feedback(self, performance_metrics: PerformanceMetrics, conversation_context: Dict = None) -> List[FeedbackSuggestion]:
        """Generate personalized feedback suggestions"""
        suggestions = []
        
        # Analyze each technique area
        for technique, score in performance_metrics.technique_usage.items():
            if score < 0.3:
                priority = 'high'
                level = 'low'
            elif score < 0.6:
                priority = 'medium'
                level = 'medium'
            else:
                continue  # Good performance, no suggestion needed
            
            if technique in self.feedback_templates:
                template = self.feedback_templates[technique][level]
                
                suggestion = FeedbackSuggestion(
                    category=technique.replace('_', ' ').title(),
                    priority=priority,
                    message=template['message'],
                    specific_examples=self._get_specific_examples(technique, conversation_context),
                    improvement_tips=template['tips']
                )
                suggestions.append(suggestion)
        
        # Add overall performance feedback
        if performance_metrics.overall_rating in ['poor', 'needs_improvement']:
            suggestions.append(self._generate_overall_feedback(performance_metrics))
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        suggestions.sort(key=lambda x: priority_order[x.priority])
        
        return suggestions
    
    def _get_specific_examples(self, technique: str, conversation_context: Dict = None) -> List[str]:
        """Get specific examples from the conversation"""
        if not conversation_context:
            return []
        
        examples = []
        
        if technique == 'rapport_building':
            examples = [
                "Instead of jumping straight to product features, try: 'How long have you been with the company?'",
                "Add personal connection: 'I've worked with other companies in your industry...'"
            ]
        elif technique == 'needs_discovery':
            examples = [
                "When they mention a challenge, ask: 'What impact does that have on your team?'",
                "Follow up with: 'How are you handling that currently?'"
            ]
        elif technique == 'value_presentation':
            examples = [
                "Instead of 'This feature...', try: 'This means you'll save 2 hours per day...'",
                "Connect to their pain: 'Remember you mentioned X? This solves that by...'"
            ]
        
        return examples[:2]  # Limit to 2 examples
    
    def _generate_overall_feedback(self, performance_metrics: PerformanceMetrics) -> FeedbackSuggestion:
        """Generate overall performance feedback"""
        if performance_metrics.overall_rating == 'poor':
            message = "Focus on fundamentals: listen more, ask better questions, and present clear value"
            priority = 'high'
            tips = [
                "Practice active listening techniques",
                "Prepare a list of discovery questions",
                "Study your product's key benefits",
                "Role-play common scenarios"
            ]
        else:  # needs_improvement
            message = "Good foundation, focus on consistency and advanced techniques"
            priority = 'medium'
            tips = [
                "Be more consistent with proven techniques",
                "Practice handling objections proactively",
                "Work on your closing confidence",
                "Develop stronger value propositions"
            ]
        
        return FeedbackSuggestion(
            category="Overall Performance",
            priority=priority,
            message=message,
            specific_examples=[],
            improvement_tips=tips
        )

class ProgressTracker:
    """Track improvement over time"""
    
    def __init__(self, storage_path: str = "./training/validation/progress.json"):
        self.storage_path = storage_path
        self.progress_data = self._load_progress_data()
    
    def _load_progress_data(self) -> Dict:
        """Load existing progress data"""
        if Path(self.storage_path).exists():
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        return {"sessions": [], "improvements": {}}
    
    def record_session(self, user_id: str, performance_metrics: PerformanceMetrics, timestamp: str = None):
        """Record a training session"""
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        session_data = {
            "user_id": user_id,
            "timestamp": timestamp,
            "overall_score": performance_metrics.conversation_score,
            "rating": performance_metrics.overall_rating,
            "technique_scores": performance_metrics.technique_usage,
            "objection_handling": performance_metrics.objection_handling,
            "closing_effectiveness": performance_metrics.closing_effectiveness
        }
        
        self.progress_data["sessions"].append(session_data)
        self._save_progress_data()
    
    def get_improvement_trends(self, user_id: str, days: int = 30) -> Dict:
        """Get improvement trends for a user"""
        user_sessions = [
            session for session in self.progress_data["sessions"]
            if session["user_id"] == user_id
        ]
        
        if len(user_sessions) < 2:
            return {"message": "Need more sessions to show trends"}
        
        # Sort by timestamp
        user_sessions.sort(key=lambda x: x["timestamp"])
        
        # Calculate trends
        first_sessions = user_sessions[:3]  # First 3 sessions
        recent_sessions = user_sessions[-3:]  # Last 3 sessions
        
        first_avg = np.mean([s["overall_score"] for s in first_sessions])
        recent_avg = np.mean([s["overall_score"] for s in recent_sessions])
        
        improvement = recent_avg - first_avg
        
        # Technique-specific trends
        technique_trends = {}
        for technique in self.progress_data.get("technique_scores", {}).keys():
            first_technique_avg = np.mean([s["technique_scores"].get(technique, 0) for s in first_sessions])
            recent_technique_avg = np.mean([s["technique_scores"].get(technique, 0) for s in recent_sessions])
            technique_trends[technique] = recent_technique_avg - first_technique_avg
        
        return {
            "overall_improvement": improvement,
            "improvement_percentage": (improvement / first_avg) * 100 if first_avg > 0 else 0,
            "technique_trends": technique_trends,
            "sessions_analyzed": len(user_sessions),
            "current_level": recent_sessions[-1]["rating"]
        }
    
    def _save_progress_data(self):
        """Save progress data to file"""
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.progress_data, f, indent=2)

def main():
    """Demo feedback system"""
    logger.info("Initializing Sales Feedback System")
    
    # Initialize components
    classifier = SalesPerformanceClassifier()
    feedback_generator = FeedbackGenerator()
    progress_tracker = ProgressTracker()
    
    # Mock conversation data
    mock_conversation = "Customer said they're interested but worried about price. User responded with features list."
    mock_user_responses = [
        "Our product has many great features including X, Y, and Z",
        "The price is competitive in the market",
        "Let me know if you have any questions"
    ]
    
    # Analyze performance
    performance = classifier.analyze_conversation(mock_conversation, mock_user_responses)
    logger.info(f"Performance analysis: {performance.overall_rating} ({performance.conversation_score:.2f})")
    
    # Generate feedback
    suggestions = feedback_generator.generate_feedback(performance)
    logger.info(f"Generated {len(suggestions)} feedback suggestions")
    
    for suggestion in suggestions:
        logger.info(f"- {suggestion.category} ({suggestion.priority}): {suggestion.message}")
    
    # Record session
    progress_tracker.record_session("demo_user", performance)
    logger.info("Session recorded for progress tracking")

if __name__ == "__main__":
    main()