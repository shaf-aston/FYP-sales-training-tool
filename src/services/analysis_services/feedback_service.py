"""
Refactored Feedback Service - Orchestration Layer
Coordinates modular feedback analysis components for comprehensive sales training insights

This refactored version uses modular components for improved maintainability:
- ConversationAnalyzer: Basic conversation metrics and flow
- CommunicationAnalyzer: Communication style and effectiveness
- SalesProcessAnalyzer: Sales methodology and process adherence
- EmotionalIntelligenceAnalyzer: EQ and rapport building
- FeedbackGenerator: Feedback compilation and recommendations
"""

import logging
from typing import Dict, List, Optional, Any
import time
import asyncio

from .feedback_models import FeedbackSummary
from .conversation_analyzer import ConversationAnalyzer
from .communication_analyzer import CommunicationAnalyzer
from .sales_process_analyzer import SalesProcessAnalyzer
from .emotional_intelligence_analyzer import EmotionalIntelligenceAnalyzer
from .feedback_generator import FeedbackGenerator

logger = logging.getLogger(__name__)

class FeedbackAnalyticsService:
    """
    Refactored feedback analytics service
    Orchestrates multiple specialized analyzers for comprehensive sales training feedback
    """

    def __init__(self):
        """Initialize the service with all component analyzers"""
        self.conversation_analyzer = ConversationAnalyzer()
        self.communication_analyzer = CommunicationAnalyzer()
        self.sales_process_analyzer = SalesProcessAnalyzer()
        self.emotional_intelligence_analyzer = EmotionalIntelligenceAnalyzer()
        self.feedback_generator = FeedbackGenerator()

        self.analysis_count = 0
        self.total_processing_time = 0.0

        self.session_analyses = {}
        self.user_feedback_history = {}

        logger.info("✅ Feedback Analytics Service initialized with modular components")

    async def analyze_conversation(self, session_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive feedback analysis using all modular components

        Args:
            session_data: Session data including conversation history
            user_id: User identifier

        Returns:
            Complete analysis results with feedback summary
        """
        start_time = time.time()
        session_id = session_data.get('session_id', f"session_{int(time.time())}")

        try:
            logger.info(f"Starting comprehensive feedback analysis for session {session_id}")

            conversation_history = session_data.get('conversation_history', [])
            persona_data = session_data.get('persona_data', {})

            if not conversation_history:
                raise ValueError("No conversation history provided for analysis")

            analysis_results = await self._run_parallel_analysis(
                conversation_history, persona_data
            )

            feedback_summary = self.feedback_generator.generate_feedback_summary(
                session_id=session_id,
                user_id=user_id,
                conversation_metrics=analysis_results['conversation_metrics'],
                communication_analysis=analysis_results['communication_analysis'],
                sales_process_analysis=analysis_results['sales_process_analysis'],
                emotional_intelligence_analysis=analysis_results['emotional_intelligence_analysis'],
                persona_data=persona_data
            )

            analysis_record = {
                'session_id': session_id,
                'user_id': user_id,
                'analysis_timestamp': time.time(),
                'feedback_summary': feedback_summary.to_dict(),
                'component_results': {
                    'conversation_metrics': analysis_results['conversation_metrics'].to_dict(),
                    'communication_analysis': analysis_results['communication_analysis'].to_dict(),
                    'sales_process_analysis': analysis_results['sales_process_analysis'].to_dict(),
                    'emotional_intelligence_analysis': analysis_results['emotional_intelligence_analysis'].to_dict()
                }
            }

            self.session_analyses[session_id] = analysis_record

            if user_id not in self.user_feedback_history:
                self.user_feedback_history[user_id] = []
            self.user_feedback_history[user_id].append(analysis_record)

            processing_time = time.time() - start_time
            self._update_performance_metrics(processing_time)

            response = self._format_legacy_response(feedback_summary, analysis_results)

            logger.info(f"✅ Feedback analysis completed in {processing_time:.2f}s")
            logger.info(f"Generated {len(feedback_summary.feedback_items)} feedback items")

            return response

        except Exception as e:
            logger.error(f"❌ Feedback analysis failed for session {session_id}: {e}")
            return {
                'error': str(e),
                'session_id': session_id,
                'user_id': user_id,
                'analysis_timestamp': time.time()
            }

    async def _run_parallel_analysis(self, conversation_history: List[Dict], persona_data: Dict) -> Dict[str, Any]:
        """Run all analysis components in parallel for efficiency"""

        conversation_task = asyncio.create_task(
            self._run_conversation_analysis(conversation_history)
        )

        communication_task = asyncio.create_task(
            self._run_communication_analysis(conversation_history)
        )

        sales_process_task = asyncio.create_task(
            self._run_sales_process_analysis(conversation_history, persona_data)
        )

        emotional_intelligence_task = asyncio.create_task(
            self._run_emotional_intelligence_analysis(conversation_history, persona_data)
        )

        conversation_metrics = await conversation_task
        communication_analysis = await communication_task
        sales_process_analysis = await sales_process_task
        emotional_intelligence_analysis = await emotional_intelligence_task

        return {
            'conversation_metrics': conversation_metrics,
            'communication_analysis': communication_analysis,
            'sales_process_analysis': sales_process_analysis,
            'emotional_intelligence_analysis': emotional_intelligence_analysis
        }

    async def _run_conversation_analysis(self, conversation_history: List[Dict]):
        """Run conversation analysis"""
        return self.conversation_analyzer.analyze(conversation_history)

    async def _run_communication_analysis(self, conversation_history: List[Dict]):
        """Run communication analysis"""
        return self.communication_analyzer.analyze(conversation_history)

    async def _run_sales_process_analysis(self, conversation_history: List[Dict], persona_data: Dict):
        """Run sales process analysis"""
        return self.sales_process_analyzer.analyze(conversation_history, persona_data)

    async def _run_emotional_intelligence_analysis(self, conversation_history: List[Dict], persona_data: Dict):
        """Run emotional intelligence analysis"""
        return self.emotional_intelligence_analyzer.analyze(conversation_history, persona_data)

    def _format_legacy_response(self, feedback_summary: FeedbackSummary,
                              analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """Format response to maintain backward compatibility"""
        return {
            'session_id': feedback_summary.session_id,
            'user_id': feedback_summary.user_id,
            'analysis_timestamp': feedback_summary.timestamp,
            'overall_score': feedback_summary.overall_score,
            'overall_rating': feedback_summary.overall_rating,
            'key_strengths': feedback_summary.key_strengths,
            'priority_improvements': feedback_summary.priority_improvements,
            'feedback_items': [item.to_dict() for item in feedback_summary.feedback_items],
            'conversation_metrics': feedback_summary.conversation_metrics.to_dict(),
            'communication_analysis': feedback_summary.communication_analysis.to_dict(),
            'sales_process_analysis': feedback_summary.sales_process_analysis.to_dict(),
            'emotional_intelligence': feedback_summary.emotional_intelligence_analysis.to_dict(),
            'overall_scores': {
                'communication_score': feedback_summary.communication_analysis.effectiveness_rating,
                'emotional_intelligence_score': feedback_summary.emotional_intelligence_analysis.overall_eq_score,
                'technical_skills_score': feedback_summary.sales_process_analysis.process_score,
                'sales_process_score': feedback_summary.sales_process_analysis.process_score,
                'weighted_average': feedback_summary.overall_score,
                'performance_grade': feedback_summary.overall_rating
            }
        }

    def _update_performance_metrics(self, processing_time: float):
        """Update service performance metrics"""
        self.analysis_count += 1
        self.total_processing_time += processing_time

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive service performance metrics"""
        avg_time = self.total_processing_time / self.analysis_count if self.analysis_count > 0 else 0

        return {
            'service_info': {
                'version': '2.0_modular',
                'components': ['ConversationAnalyzer', 'CommunicationAnalyzer',
                             'SalesProcessAnalyzer', 'EmotionalIntelligenceAnalyzer',
                             'FeedbackGenerator'],
                'architecture': 'modular_orchestration'
            },
            'performance': {
                'total_analyses': self.analysis_count,
                'total_processing_time': f"{self.total_processing_time:.2f}s",
                'average_processing_time': f"{avg_time:.2f}s",
                'analyses_per_minute': round(60 / avg_time, 1) if avg_time > 0 else 0
            },
            'status': 'active'
        }

    def get_detailed_feedback_insights(self, session_id: str) -> Dict[str, Any]:
        """Get detailed insights for a specific session"""
        if session_id not in self.session_analyses:
            return {'error': 'Session not found'}

        analysis_record = self.session_analyses[session_id]
        feedback_summary = FeedbackSummary.from_dict(analysis_record['feedback_summary'])

        insights = self.feedback_generator.get_feedback_insights(feedback_summary)

        component_insights = {
            'conversation_insights': self.conversation_analyzer.get_conversation_insights(
                feedback_summary.conversation_metrics
            ),
            'communication_insights': self.communication_analyzer.get_communication_insights(
                feedback_summary.communication_analysis
            ),
            'sales_process_insights': self.sales_process_analyzer.get_process_insights(
                feedback_summary.sales_process_analysis
            ),
            'eq_insights': self.emotional_intelligence_analyzer.get_eq_insights(
                feedback_summary.emotional_intelligence_analysis
            )
        }

        return {
            'session_id': session_id,
            'feedback_summary': insights,
            'component_insights': component_insights,
            'analysis_timestamp': analysis_record['analysis_timestamp']
        }

    def get_analytics_dashboard(self, user_id: str = None, timeframe_days: int = 30) -> Dict[str, Any]:
        """Legacy analytics dashboard method"""
        cutoff_time = time.time() - (timeframe_days * 24 * 3600)

        if user_id:
            if user_id not in self.user_feedback_history:
                return {"error": "User not found"}

            user_sessions = [s for s in self.user_feedback_history[user_id]
                           if s.get("analysis_timestamp", 0) > cutoff_time]

            if not user_sessions:
                return {"error": "No sessions found in timeframe"}

            avg_score = sum(s['feedback_summary']['overall_score'] for s in user_sessions) / len(user_sessions)

            return {
                "user_id": user_id,
                "timeframe_days": timeframe_days,
                "total_sessions": len(user_sessions),
                "average_score": round(avg_score, 1),
                "score_trend": "stable",
                "improvement_rate": 0.0,
                "category_breakdown": {},
                "recent_achievements": []
            }
        else:
            total_sessions = len(self.session_analyses)
            recent_sessions = [s for s in self.session_analyses.values()
                             if s.get("analysis_timestamp", 0) > cutoff_time]

            all_scores = [s['feedback_summary']['overall_score'] for s in recent_sessions]
            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

            return {
                "system_metrics": {
                    "total_sessions_analyzed": total_sessions,
                    "sessions_in_timeframe": len(recent_sessions),
                    "average_system_score": round(avg_score, 1),
                    "active_users": len(self.user_feedback_history),
                    "total_feedback_items": sum(len(s['feedback_summary'].get('feedback_items', []))
                                              for s in self.session_analyses.values())
                },
                "performance_distribution": {},
                "common_improvement_areas": [],
                "success_rate_by_category": {}
            }

    def generate_improvement_plan(self, user_id: str, timeframe_days: int = 30) -> Dict[str, Any]:
        """Legacy improvement plan generation"""
        if user_id not in self.user_feedback_history:
            return {"error": "No feedback history found for user"}

        recent_sessions = self.user_feedback_history[user_id][-5:]

        if not recent_sessions:
            return {"error": "No recent sessions found"}

        avg_score = sum(s['feedback_summary']['overall_score'] for s in recent_sessions) / len(recent_sessions)

        return {
            "user_id": user_id,
            "plan_created": time.time(),
            "timeframe_days": timeframe_days,
            "current_level": "intermediate" if avg_score >= 70 else "developing" if avg_score >= 50 else "beginner",
            "focus_areas": ["Communication", "Sales Process", "Emotional Intelligence"][:2],
            "weekly_goals": [],
            "recommended_scenarios": [],
            "success_metrics": {
                "target_overall_score": 75,
                "minimum_sessions_per_week": 3,
                "target_improvement_areas": 2,
                "success_indicators": [
                    "Consistent scores above 70% in focus areas",
                    "Successful objection handling",
                    "Positive feedback on communication"
                ]
            },
            "resources": []
        }


feedback_service = FeedbackAnalyticsService()

def analyze_conversation_feedback(session_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Legacy function for backward compatibility"""
    import asyncio
    service = feedback_service
    return asyncio.run(service.analyze_conversation(session_data, user_id))