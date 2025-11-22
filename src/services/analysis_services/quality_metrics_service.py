"""
Quality Metrics Store - Advanced Analytics for Training Performance

This service provides comprehensive quality metrics storage and analysis including:
- Performance scoring and tracking over time
- Skill-based analytics (communication, persuasion, empathy, etc.)
- Improvement recommendations and personalized insights
- Comparative analysis and benchmarking
- Detailed reporting and visualization data

Features:
- SQLite database for reliable metric storage
- Time-series performance tracking
- Multi-dimensional skill assessment
- Automated improvement recommendations
- Statistical analysis and trend detection
- Export capabilities for reporting
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from contextlib import contextmanager
import threading
import statistics
from collections import defaultdict
from config.settings import QUALITY_DB_PATH

logger = logging.getLogger(__name__)

@dataclass
class QualityMetric:
    """Represents a single quality measurement"""
    metric_id: str
    session_id: str
    user_id: str
    metric_type: str
    metric_category: str
    score: float
    score_scale: str
    measurement_context: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    source: str = 'automated' 

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QualityMetric':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class ImprovementRecommendation:
    """Represents an improvement recommendation"""
    recommendation_id: str
    user_id: str
    skill_area: str
    priority: str
    recommendation_text: str
    action_items: List[str]
    target_improvement: float
    timeframe: str
    based_on_sessions: List[str]
    created_at: datetime
    status: str = 'active' 
    progress: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImprovementRecommendation':
        """Create from dictionary"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

@dataclass
class SkillAssessment:
    """Comprehensive skill assessment"""
    assessment_id: str
    user_id: str
    assessment_date: datetime
    overall_score: float
    skill_scores: Dict[str, float]
    percentile_rankings: Dict[str, float]
    improvement_areas: List[str]
    strengths: List[str]
    assessment_summary: str
    recommendations: List[str]
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['assessment_date'] = self.assessment_date.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillAssessment':
        """Create from dictionary"""
        data['assessment_date'] = datetime.fromisoformat(data['assessment_date'])
        return cls(**data)

class QualityMetricsDatabase:
    """Database manager for quality metrics storage"""
    
    def __init__(self, db_path: str | Path = None):
        """Initialize database connection"""
        resolved = Path(db_path) if db_path else Path(QUALITY_DB_PATH)
        self.db_path = resolved
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_database()

    @contextmanager
    def get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            self._local.connection.commit()

    def _init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quality_metrics (
                    metric_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_category TEXT NOT NULL,
                    score REAL NOT NULL,
                    score_scale TEXT NOT NULL,
                    measurement_context TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    confidence REAL,
                    source TEXT DEFAULT 'automated',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS improvement_recommendations (
                    recommendation_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    skill_area TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    recommendation_text TEXT NOT NULL,
                    action_items TEXT NOT NULL,  -- JSON array
                    target_improvement REAL NOT NULL,
                    timeframe TEXT NOT NULL,
                    based_on_sessions TEXT NOT NULL,  -- JSON array
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    progress REAL,
                    metadata TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS skill_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    assessment_date TEXT NOT NULL,
                    overall_score REAL NOT NULL,
                    skill_scores TEXT NOT NULL,  -- JSON object
                    percentile_rankings TEXT,    -- JSON object
                    improvement_areas TEXT,      -- JSON array
                    strengths TEXT,              -- JSON array
                    assessment_summary TEXT,
                    recommendations TEXT,        -- JSON array
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS performance_benchmarks (
                    benchmark_id TEXT PRIMARY KEY,
                    metric_type TEXT NOT NULL,
                    skill_level TEXT NOT NULL,  -- 'beginner', 'intermediate', 'advanced'
                    benchmark_score REAL NOT NULL,
                    percentile_25 REAL,
                    percentile_50 REAL,
                    percentile_75 REAL,
                    percentile_90 REAL,
                    sample_size INTEGER,
                    last_updated TEXT NOT NULL,
                    metadata TEXT
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_user_id ON quality_metrics (user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_session_id ON quality_metrics (session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_type ON quality_metrics (metric_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON quality_metrics (timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_user_id ON improvement_recommendations (user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_recommendations_status ON improvement_recommendations (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assessments_user_id ON skill_assessments (user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assessments_date ON skill_assessments (assessment_date)')
            
            logger.info("Quality metrics database initialized successfully")

    def store_metric(self, metric: QualityMetric) -> bool:
        """Store a quality metric"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO quality_metrics (
                        metric_id, session_id, user_id, metric_type, metric_category,
                        score, score_scale, measurement_context, timestamp,
                        metadata, confidence, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metric.metric_id,
                    metric.session_id,
                    metric.user_id,
                    metric.metric_type,
                    metric.metric_category,
                    metric.score,
                    metric.score_scale,
                    metric.measurement_context,
                    metric.timestamp.isoformat(),
                    json.dumps(metric.metadata) if metric.metadata else None,
                    metric.confidence,
                    metric.source
                ))
                logger.debug(f"Stored metric {metric.metric_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to store metric: {e}")
            return False

    def store_recommendation(self, recommendation: ImprovementRecommendation) -> bool:
        """Store an improvement recommendation"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO improvement_recommendations (
                        recommendation_id, user_id, skill_area, priority,
                        recommendation_text, action_items, target_improvement,
                        timeframe, based_on_sessions, created_at, status,
                        progress, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recommendation.recommendation_id,
                    recommendation.user_id,
                    recommendation.skill_area,
                    recommendation.priority,
                    recommendation.recommendation_text,
                    json.dumps(recommendation.action_items),
                    recommendation.target_improvement,
                    recommendation.timeframe,
                    json.dumps(recommendation.based_on_sessions),
                    recommendation.created_at.isoformat(),
                    recommendation.status,
                    recommendation.progress,
                    json.dumps(recommendation.metadata) if recommendation.metadata else None
                ))
                logger.info(f"Stored recommendation {recommendation.recommendation_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to store recommendation: {e}")
            return False

    def store_assessment(self, assessment: SkillAssessment) -> bool:
        """Store a skill assessment"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO skill_assessments (
                        assessment_id, user_id, assessment_date, overall_score,
                        skill_scores, percentile_rankings, improvement_areas,
                        strengths, assessment_summary, recommendations, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    assessment.assessment_id,
                    assessment.user_id,
                    assessment.assessment_date.isoformat(),
                    assessment.overall_score,
                    json.dumps(assessment.skill_scores),
                    json.dumps(assessment.percentile_rankings) if assessment.percentile_rankings else None,
                    json.dumps(assessment.improvement_areas),
                    json.dumps(assessment.strengths),
                    assessment.assessment_summary,
                    json.dumps(assessment.recommendations),
                    json.dumps(assessment.metadata) if assessment.metadata else None
                ))
                logger.info(f"Stored assessment {assessment.assessment_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to store assessment: {e}")
            return False

    def get_user_metrics(self, user_id: str, 
                        metric_type: Optional[str] = None,
                        start_date: Optional[datetime] = None,
                        end_date: Optional[datetime] = None,
                        limit: int = 1000) -> List[QualityMetric]:
        """Get quality metrics for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT * FROM quality_metrics WHERE user_id = ?'
                params = [user_id]
                
                if metric_type:
                    query += ' AND metric_type = ?'
                    params.append(metric_type)
                
                if start_date:
                    query += ' AND timestamp >= ?'
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += ' AND timestamp <= ?'
                    params.append(end_date.isoformat())
                
                query += ' ORDER BY timestamp DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                metrics = []
                for row in cursor.fetchall():
                    metric_data = {
                        'metric_id': row['metric_id'],
                        'session_id': row['session_id'],
                        'user_id': row['user_id'],
                        'metric_type': row['metric_type'],
                        'metric_category': row['metric_category'],
                        'score': row['score'],
                        'score_scale': row['score_scale'],
                        'measurement_context': row['measurement_context'],
                        'timestamp': datetime.fromisoformat(row['timestamp']),
                        'metadata': json.loads(row['metadata']) if row['metadata'] else None,
                        'confidence': row['confidence'],
                        'source': row['source']
                    }
                    metrics.append(QualityMetric(**metric_data))
                
                return metrics
        except Exception as e:
            logger.error(f"Failed to get user metrics: {e}")
            return []

    def get_user_recommendations(self, user_id: str, 
                               status: Optional[str] = None,
                               limit: int = 50) -> List[ImprovementRecommendation]:
        """Get improvement recommendations for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT * FROM improvement_recommendations WHERE user_id = ?'
                params = [user_id]
                
                if status:
                    query += ' AND status = ?'
                    params.append(status)
                
                query += ' ORDER BY created_at DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                recommendations = []
                for row in cursor.fetchall():
                    rec_data = {
                        'recommendation_id': row['recommendation_id'],
                        'user_id': row['user_id'],
                        'skill_area': row['skill_area'],
                        'priority': row['priority'],
                        'recommendation_text': row['recommendation_text'],
                        'action_items': json.loads(row['action_items']),
                        'target_improvement': row['target_improvement'],
                        'timeframe': row['timeframe'],
                        'based_on_sessions': json.loads(row['based_on_sessions']),
                        'created_at': datetime.fromisoformat(row['created_at']),
                        'status': row['status'],
                        'progress': row['progress'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else None
                    }
                    recommendations.append(ImprovementRecommendation(**rec_data))
                
                return recommendations
        except Exception as e:
            logger.error(f"Failed to get user recommendations: {e}")
            return []

    def get_user_assessments(self, user_id: str, limit: int = 10) -> List[SkillAssessment]:
        """Get skill assessments for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM skill_assessments 
                    WHERE user_id = ? 
                    ORDER BY assessment_date DESC 
                    LIMIT ?
                ''', (user_id, limit))
                
                assessments = []
                for row in cursor.fetchall():
                    assessment_data = {
                        'assessment_id': row['assessment_id'],
                        'user_id': row['user_id'],
                        'assessment_date': datetime.fromisoformat(row['assessment_date']),
                        'overall_score': row['overall_score'],
                        'skill_scores': json.loads(row['skill_scores']),
                        'percentile_rankings': json.loads(row['percentile_rankings']) if row['percentile_rankings'] else None,
                        'improvement_areas': json.loads(row['improvement_areas']),
                        'strengths': json.loads(row['strengths']),
                        'assessment_summary': row['assessment_summary'],
                        'recommendations': json.loads(row['recommendations']),
                        'metadata': json.loads(row['metadata']) if row['metadata'] else None
                    }
                    assessments.append(SkillAssessment(**assessment_data))
                
                return assessments
        except Exception as e:
            logger.error(f"Failed to get user assessments: {e}")
            return []

class QualityMetricsStore:
    """
    High-level quality metrics management service providing comprehensive
    performance tracking, analysis, and improvement recommendations
    """
    
    def __init__(self, db_path: str | Path = None):
        """Initialize the quality metrics store"""
        self.db = QualityMetricsDatabase(db_path)
        self.skill_categories = {
            'communication': ['clarity', 'active_listening', 'questioning', 'rapport_building'],
            'persuasion': ['value_proposition', 'objection_handling', 'closing_techniques', 'influence'],
            'empathy': ['emotional_intelligence', 'customer_understanding', 'adaptability'],
            'technical': ['product_knowledge', 'solution_matching', 'feature_explanation'],
            'process': ['needs_assessment', 'follow_up', 'time_management', 'organization']
        }
        logger.info("Quality Metrics Store initialized")

    def record_session_metrics(self, 
                             session_id: str,
                             user_id: str,
                             feedback_scores: Dict[str, float],
                             conversation_analysis: Optional[Dict[str, Any]] = None,
                             source: str = 'automated') -> bool:
        """Record comprehensive metrics from a completed session"""
        try:
            timestamp = datetime.now(UTC)
            
            for skill, score in feedback_scores.items():
                metric_id = str(uuid.uuid4())
                
                category = 'skill'
                for cat, skills in self.skill_categories.items():
                    if skill in skills:
                        category = cat
                        break
                
                metric = QualityMetric(
                    metric_id=metric_id,
                    session_id=session_id,
                    user_id=user_id,
                    metric_type=skill,
                    metric_category=category,
                    score=score,
                    score_scale='percentage',
                    measurement_context='session_level',
                    timestamp=timestamp,
                    metadata=conversation_analysis,
                    confidence=0.85,
                    source=source
                )
                
                self.db.store_metric(metric)
            
            logger.info(f"Recorded session metrics for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to record session metrics: {e}")
            return False

    def generate_skill_assessment(self, user_id: str, 
                                days_back: int = 30) -> Optional[SkillAssessment]:
        """Generate comprehensive skill assessment based on recent performance"""
        try:
            start_date = datetime.now(UTC) - timedelta(days=days_back)
            metrics = self.db.get_user_metrics(
                user_id=user_id,
                start_date=start_date
            )
            
            if not metrics:
                logger.warning(f"No metrics found for user {user_id}")
                return None
            
            skill_scores = {}
            skill_metrics = defaultdict(list)
            
            for metric in metrics:
                skill_metrics[metric.metric_type].append(metric.score)
            
            for skill, scores in skill_metrics.items():
                skill_scores[skill] = statistics.mean(scores)
            
            overall_score = statistics.mean(skill_scores.values()) if skill_scores else 0
            
            percentile_rankings = {}
            for skill, score in skill_scores.items():
                percentile_rankings[skill] = min(score, 95.0)
            
            sorted_skills = sorted(skill_scores.items(), key=lambda x: x[1])
            improvement_areas = [skill for skill, score in sorted_skills[:3] if score < 70]
            strengths = [skill for skill, score in sorted_skills[-3:] if score >= 80]
            
            summary = self._generate_assessment_summary(
                overall_score, skill_scores, improvement_areas, strengths
            )
            
            recommendations = self._generate_skill_recommendations(
                skill_scores, improvement_areas
            )
            
            assessment = SkillAssessment(
                assessment_id=str(uuid.uuid4()),
                user_id=user_id,
                assessment_date=datetime.now(UTC),
                overall_score=overall_score,
                skill_scores=skill_scores,
                percentile_rankings=percentile_rankings,
                improvement_areas=improvement_areas,
                strengths=strengths,
                assessment_summary=summary,
                recommendations=recommendations,
                metadata={
                    'metrics_analyzed': len(metrics),
                    'assessment_period_days': days_back,
                    'sessions_included': len(set(m.session_id for m in metrics))
                }
            )
            
            self.db.store_assessment(assessment)
            logger.info(f"Generated skill assessment for user {user_id}")
            return assessment
            
        except Exception as e:
            logger.error(f"Failed to generate skill assessment: {e}")
            return None

    def generate_improvement_recommendations(self, user_id: str,
                                           focus_area: Optional[str] = None) -> List[ImprovementRecommendation]:
        """Generate personalized improvement recommendations"""
        try:
            metrics = self.db.get_user_metrics(user_id, limit=500)
            assessments = self.db.get_user_assessments(user_id, limit=3)
            
            if not metrics:
                return []
            
            performance_analysis = self._analyze_performance_trends(metrics)
            
            recommendations = []
            
            skill_averages = defaultdict(list)
            for metric in metrics[-100:]:
                skill_averages[metric.metric_type].append(metric.score)
            
            for skill, scores in skill_averages.items():
                avg_score = statistics.mean(scores)
                
                if focus_area and skill != focus_area:
                    continue
                
                if avg_score < 70:
                    recommendation = self._create_improvement_recommendation(
                        user_id=user_id,
                        skill_area=skill,
                        current_score=avg_score,
                        performance_trend=performance_analysis.get(skill, 'stable'),
                        recent_sessions=list(set(m.session_id for m in metrics[-50:]))
                    )
                    
                    if recommendation:
                        self.db.store_recommendation(recommendation)
                        recommendations.append(recommendation)
            
            logger.info(f"Generated {len(recommendations)} recommendations for user {user_id}")
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return []

    def get_performance_analytics(self, user_id: str, 
                                days_back: int = 90) -> Dict[str, Any]:
        """Get comprehensive performance analytics"""
        try:
            start_date = datetime.now(UTC) - timedelta(days=days_back)
            metrics = self.db.get_user_metrics(
                user_id=user_id,
                start_date=start_date
            )
            
            if not metrics:
                return {}
            
            skill_data = defaultdict(list)
            for metric in metrics:
                skill_data[metric.metric_type].append({
                    'score': metric.score,
                    'timestamp': metric.timestamp,
                    'session_id': metric.session_id
                })
            
            skill_analytics = {}
            for skill, data in skill_data.items():
                scores = [d['score'] for d in data]
                
                skill_analytics[skill] = {
                    'current_average': statistics.mean(scores),
                    'best_score': max(scores),
                    'worst_score': min(scores),
                    'score_variance': statistics.variance(scores) if len(scores) > 1 else 0,
                    'improvement_trend': self._calculate_trend(data),
                    'total_sessions': len(set(d['session_id'] for d in data)),
                    'score_distribution': self._calculate_score_distribution(scores)
                }
            
            all_scores = [metric.score for metric in metrics]
            overall_analytics = {
                'overall_average': statistics.mean(all_scores),
                'total_metrics': len(metrics),
                'total_sessions': len(set(m.session_id for m in metrics)),
                'improvement_rate': self._calculate_overall_improvement_rate(metrics),
                'consistency_score': self._calculate_consistency_score(all_scores),
                'skill_balance': self._calculate_skill_balance(skill_analytics)
            }
            
            return {
                'skill_analytics': skill_analytics,
                'overall_analytics': overall_analytics,
                'analysis_period': {
                    'days': days_back,
                    'start_date': start_date.isoformat(),
                    'end_date': datetime.now(UTC).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance analytics: {e}")
            return {}

    def get_progress_tracking(self, user_id: str, skill: str) -> Dict[str, Any]:
        """Get detailed progress tracking for a specific skill"""
        try:
            metrics = self.db.get_user_metrics(user_id, metric_type=skill, limit=200)
            
            if not metrics:
                return {}
            
            metrics.sort(key=lambda m: m.timestamp)
            
            time_series = []
            for metric in metrics:
                time_series.append({
                    'date': metric.timestamp.isoformat(),
                    'score': metric.score,
                    'session_id': metric.session_id
                })
            
            scores = [m.score for m in metrics]
            recent_scores = scores[-10:] if len(scores) >= 10 else scores
            early_scores = scores[:10] if len(scores) >= 10 else scores[:len(scores)//2] if len(scores) > 2 else scores
            
            progress_info = {
                'skill': skill,
                'total_measurements': len(metrics),
                'current_score': scores[-1] if scores else 0,
                'starting_score': scores[0] if scores else 0,
                'best_score': max(scores) if scores else 0,
                'recent_average': statistics.mean(recent_scores) if recent_scores else 0,
                'early_average': statistics.mean(early_scores) if early_scores else 0,
                'improvement': (statistics.mean(recent_scores) - statistics.mean(early_scores)) if len(scores) > 5 else 0,
                'trend': self._calculate_trend([{'score': s, 'timestamp': m.timestamp} for s, m in zip(scores, metrics)]),
                'time_series': time_series,
                'sessions_tracked': len(set(m.session_id for m in metrics)),
                'tracking_period': {
                    'start': metrics[0].timestamp.isoformat(),
                    'end': metrics[-1].timestamp.isoformat(),
                    'days': (metrics[-1].timestamp - metrics[0].timestamp).days
                }
            }
            
            return progress_info
            
        except Exception as e:
            logger.error(f"Failed to get progress tracking: {e}")
            return {}

    def _generate_assessment_summary(self, overall_score: float, 
                                   skill_scores: Dict[str, float],
                                   improvement_areas: List[str],
                                   strengths: List[str]) -> str:
        """Generate a comprehensive assessment summary"""
        summary_parts = []
        
        if overall_score >= 85:
            summary_parts.append("Excellent overall performance with strong skills across multiple areas.")
        elif overall_score >= 70:
            summary_parts.append("Good overall performance with room for targeted improvements.")
        elif overall_score >= 55:
            summary_parts.append("Average performance with several areas requiring focused development.")
        else:
            summary_parts.append("Performance indicates need for comprehensive skill development.")
        
        if strengths:
            summary_parts.append(f"Key strengths include: {', '.join(strengths)}.")
        
        if improvement_areas:
            summary_parts.append(f"Priority improvement areas: {', '.join(improvement_areas)}.")
        
        return " ".join(summary_parts)

    def _generate_skill_recommendations(self, skill_scores: Dict[str, float],
                                      improvement_areas: List[str]) -> List[str]:
        """Generate specific skill-based recommendations"""
        recommendations = []
        
        for skill in improvement_areas:
            score = skill_scores.get(skill, 0)
            
            if skill == 'clarity':
                recommendations.append("Practice speaking more slowly and using simpler language to improve message clarity.")
            elif skill == 'active_listening':
                recommendations.append("Focus on asking follow-up questions and paraphrasing customer statements.")
            elif skill == 'objection_handling':
                recommendations.append("Study common objections and practice the acknowledge-explore-respond framework.")
            elif skill == 'value_proposition':
                recommendations.append("Work on clearly articulating how your solution solves specific customer problems.")
            elif skill == 'rapport_building':
                recommendations.append("Practice finding common ground and using mirroring techniques in conversations.")
            else:
                recommendations.append(f"Focus on improving {skill} through targeted practice and feedback.")
        
        return recommendations

    def _create_improvement_recommendation(self, user_id: str, skill_area: str,
                                        current_score: float, performance_trend: str,
                                        recent_sessions: List[str]) -> Optional[ImprovementRecommendation]:
        """Create a detailed improvement recommendation"""
        try:
            if current_score < 50:
                priority = 'high'
            elif current_score < 70:
                priority = 'medium'
            else:
                priority = 'low'
            
            skill_recommendations = {
                'clarity': {
                    'text': "Improve communication clarity through structured speaking and simpler language",
                    'actions': [
                        "Practice the PREP method (Point, Reason, Example, Point)",
                        "Record yourself speaking and analyze for filler words",
                        "Use the 'explain it to a 5-year-old' test for complex concepts"
                    ]
                },
                'objection_handling': {
                    'text': "Strengthen objection handling using systematic approaches",
                    'actions': [
                        "Study the top 10 objections in your industry",
                        "Practice the acknowledge-explore-respond framework",
                        "Role-play difficult objection scenarios"
                    ]
                },
                'rapport_building': {
                    'text': "Enhance rapport building through active engagement techniques",
                    'actions': [
                        "Practice active listening and mirroring techniques",
                        "Find genuine common ground with customers",
                        "Use open-ended questions to encourage sharing"
                    ]
                }
            }
            
            default_rec = {
                'text': f"Focus on improving {skill_area} through targeted practice",
                'actions': [
                    f"Practice {skill_area} in low-stakes conversations",
                    f"Seek feedback specifically on {skill_area}",
                    f"Study best practices for {skill_area} improvement"
                ]
            }
            
            rec_info = skill_recommendations.get(skill_area, default_rec)
            
            target_improvement = min(30, 85 - current_score)
            
            recommendation = ImprovementRecommendation(
                recommendation_id=str(uuid.uuid4()),
                user_id=user_id,
                skill_area=skill_area,
                priority=priority,
                recommendation_text=rec_info['text'],
                action_items=rec_info['actions'],
                target_improvement=target_improvement,
                timeframe='short_term' if priority == 'high' else 'medium_term',
                based_on_sessions=recent_sessions,
                created_at=datetime.now(UTC),
                metadata={
                    'current_score': current_score,
                    'performance_trend': performance_trend
                }
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to create recommendation: {e}")
            return None

    def _analyze_performance_trends(self, metrics: List[QualityMetric]) -> Dict[str, str]:
        """Analyze performance trends for each skill"""
        skill_trends = {}
        skill_metrics = defaultdict(list)
        
        for metric in metrics:
            skill_metrics[metric.metric_type].append({
                'score': metric.score,
                'timestamp': metric.timestamp
            })
        
        for skill, data in skill_metrics.items():
            if len(data) < 3:
                skill_trends[skill] = 'insufficient_data'
            else:
                trend = self._calculate_trend(data)
                skill_trends[skill] = trend
        
        return skill_trends

    def _calculate_trend(self, data: List[Dict]) -> str:
        """Calculate trend direction from time series data"""
        if len(data) < 3:
            return 'insufficient_data'
        
        data.sort(key=lambda x: x['timestamp'])
        
        scores = [d['score'] for d in data]
        x_values = list(range(len(scores)))
        
        if len(scores) < 2:
            return 'stable'
        
        slope = (scores[-1] - scores[0]) / (len(scores) - 1)
        
        if slope > 2:
            return 'improving'
        elif slope < -2:
            return 'declining'
        else:
            return 'stable'

    def _calculate_score_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Calculate score distribution across ranges"""
        distribution = {
            'excellent': 0,
            'good': 0,
            'average': 0,
            'below_average': 0,
            'poor': 0
        }
        
        for score in scores:
            if score >= 90:
                distribution['excellent'] += 1
            elif score >= 80:
                distribution['good'] += 1
            elif score >= 70:
                distribution['average'] += 1
            elif score >= 60:
                distribution['below_average'] += 1
            else:
                distribution['poor'] += 1
        
        return distribution

    def _calculate_overall_improvement_rate(self, metrics: List[QualityMetric]) -> float:
        """Calculate overall improvement rate over time"""
        if len(metrics) < 10:
            return 0.0
        
        metrics.sort(key=lambda m: m.timestamp)
        
        quarter_size = len(metrics) // 4
        early_scores = [m.score for m in metrics[:quarter_size]]
        recent_scores = [m.score for m in metrics[-quarter_size:]]
        
        if not early_scores or not recent_scores:
            return 0.0
        
        early_avg = statistics.mean(early_scores)
        recent_avg = statistics.mean(recent_scores)
        
        if early_avg == 0:
            return 0.0
        
        return (recent_avg - early_avg) / early_avg * 100

    def _calculate_consistency_score(self, scores: List[float]) -> float:
        """Calculate consistency score (lower variance = higher consistency)"""
        if len(scores) < 2:
            return 100.0
        
        variance = statistics.variance(scores)
        consistency = max(0, 100 - variance)
        return min(100, consistency)

    def _calculate_skill_balance(self, skill_analytics: Dict[str, Any]) -> float:
        """Calculate how balanced skills are (less difference = better balance)"""
        if not skill_analytics:
            return 0.0
        
        averages = [data['current_average'] for data in skill_analytics.values()]
        
        if len(averages) < 2:
            return 100.0
        
        skill_range = max(averages) - min(averages)
        balance = max(0, 100 - skill_range)
        return balance

quality_metrics_store = QualityMetricsStore()

__all__ = [
    'QualityMetricsStore',
    'QualityMetric',
    'ImprovementRecommendation', 
    'SkillAssessment',
    'QualityMetricsDatabase',
    'quality_metrics_store'
]