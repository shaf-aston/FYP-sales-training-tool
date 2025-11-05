"""
Analytics Aggregator Service
Collects, aggregates, and provides insights from performance metrics,
training progress, and user behavior data.
"""
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, Counter
import statistics

from infrastructure.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)


@dataclass 
class AnalyticsEvent:
    """Individual analytics event"""
    event_id: str
    user_id: str
    session_id: str
    event_type: str  # session_start, message_sent, feedback_received, etc.
    timestamp: float
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a user or system"""
    user_id: str
    time_period: str
    sessions_completed: int
    total_conversations: int
    average_score: float
    score_trend: str  # improving, declining, stable
    top_strengths: List[str]
    improvement_areas: List[str]
    engagement_metrics: Dict[str, Any]
    learning_velocity: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsDatabase:
    """SQLite database for analytics storage"""
    
    def __init__(self, db_path: str = None):
        """Initialize analytics database"""
        if db_path is None:
            db_path = PROJECT_ROOT / "logs" / "analytics.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analytics_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    data TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # User metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_metrics (
                    metric_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metadata TEXT,
                    timestamp REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Session summaries table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_summaries (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    persona_name TEXT,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    duration_minutes REAL,
                    messages_exchanged INTEGER,
                    overall_score REAL,
                    category_scores TEXT,
                    feedback_items TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Learning progress table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learning_progress (
                    progress_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    skill_area TEXT NOT NULL,
                    baseline_score REAL,
                    current_score REAL,
                    progress_percentage REAL,
                    sessions_completed INTEGER,
                    last_updated REAL NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # System performance table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_performance (
                    record_id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    total_users INTEGER,
                    active_users INTEGER,
                    total_sessions INTEGER,
                    average_score REAL,
                    engagement_rate REAL,
                    completion_rate REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_user_time ON analytics_events(user_id, timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_user_type ON user_metrics(user_id, metric_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON session_summaries(user_id, start_time)')
            
            conn.commit()
            logger.info("Analytics database initialized successfully")
    
    def store_event(self, event: AnalyticsEvent) -> bool:
        """Store analytics event"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO analytics_events 
                    (event_id, user_id, session_id, event_type, timestamp, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    event.event_id,
                    event.user_id,
                    event.session_id,
                    event.event_type,
                    event.timestamp,
                    json.dumps(event.data)
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error storing event: {e}")
            return False
    
    def store_user_metric(self, metric_id: str, user_id: str, session_id: str,
                         metric_type: str, value: float, metadata: Dict = None) -> bool:
        """Store user performance metric"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO user_metrics
                    (metric_id, user_id, session_id, metric_type, metric_value, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    metric_id,
                    user_id, 
                    session_id,
                    metric_type,
                    value,
                    json.dumps(metadata or {}),
                    time.time()
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error storing metric: {e}")
            return False
    
    def store_session_summary(self, session_data: Dict[str, Any]) -> bool:
        """Store session summary data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO session_summaries
                    (session_id, user_id, persona_name, start_time, end_time, 
                     duration_minutes, messages_exchanged, overall_score, 
                     category_scores, feedback_items)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session_data.get('session_id'),
                    session_data.get('user_id'),
                    session_data.get('persona_name'),
                    session_data.get('start_time'),
                    session_data.get('end_time'),
                    session_data.get('duration_minutes'),
                    session_data.get('messages_exchanged'),
                    session_data.get('overall_score'),
                    json.dumps(session_data.get('category_scores', {})),
                    json.dumps(session_data.get('feedback_items', []))
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error storing session summary: {e}")
            return False
    
    def get_user_events(self, user_id: str, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get user events from specified time period"""
        cutoff_time = time.time() - (hours_back * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM analytics_events 
                    WHERE user_id = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                ''', (user_id, cutoff_time))
                
                columns = [description[0] for description in cursor.description]
                events = []
                
                for row in cursor.fetchall():
                    event = dict(zip(columns, row))
                    event['data'] = json.loads(event['data'])
                    events.append(event)
                
                return events
        except Exception as e:
            logger.error(f"Error getting user events: {e}")
            return []
    
    def get_user_metrics(self, user_id: str, metric_type: str = None, 
                        days_back: int = 30) -> List[Dict[str, Any]]:
        """Get user performance metrics"""
        cutoff_time = time.time() - (days_back * 24 * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if metric_type:
                    cursor.execute('''
                        SELECT * FROM user_metrics 
                        WHERE user_id = ? AND metric_type = ? AND timestamp > ?
                        ORDER BY timestamp DESC
                    ''', (user_id, metric_type, cutoff_time))
                else:
                    cursor.execute('''
                        SELECT * FROM user_metrics 
                        WHERE user_id = ? AND timestamp > ?
                        ORDER BY timestamp DESC
                    ''', (user_id, cutoff_time))
                
                columns = [description[0] for description in cursor.description]
                metrics = []
                
                for row in cursor.fetchall():
                    metric = dict(zip(columns, row))
                    metric['metadata'] = json.loads(metric['metadata'])
                    metrics.append(metric)
                
                return metrics
        except Exception as e:
            logger.error(f"Error getting user metrics: {e}")
            return []
    
    def get_session_summaries(self, user_id: str = None, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get session summaries"""
        cutoff_time = time.time() - (days_back * 24 * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if user_id:
                    cursor.execute('''
                        SELECT * FROM session_summaries 
                        WHERE user_id = ? AND start_time > ?
                        ORDER BY start_time DESC
                    ''', (user_id, cutoff_time))
                else:
                    cursor.execute('''
                        SELECT * FROM session_summaries 
                        WHERE start_time > ?
                        ORDER BY start_time DESC
                    ''', (cutoff_time,))
                
                columns = [description[0] for description in cursor.description]
                sessions = []
                
                for row in cursor.fetchall():
                    session = dict(zip(columns, row))
                    session['category_scores'] = json.loads(session['category_scores'] or '{}')
                    session['feedback_items'] = json.loads(session['feedback_items'] or '[]')
                    sessions.append(session)
                
                return sessions
        except Exception as e:
            logger.error(f"Error getting session summaries: {e}")
            return []


class AnalyticsAggregator:
    """Main analytics aggregation service"""
    
    def __init__(self):
        """Initialize analytics aggregator"""
        self.db = AnalyticsDatabase()
        self.event_processors = {
            'session_start': self._process_session_start,
            'session_end': self._process_session_end,
            'message_sent': self._process_message_sent,
            'feedback_generated': self._process_feedback_generated,
            'user_action': self._process_user_action
        }
    
    def track_event(self, user_id: str, session_id: str, event_type: str, 
                   data: Dict[str, Any] = None) -> bool:
        """Track analytics event"""
        event_id = f"{user_id}_{session_id}_{event_type}_{int(time.time())}"
        
        event = AnalyticsEvent(
            event_id=event_id,
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            timestamp=time.time(),
            data=data or {}
        )
        
        # Store event
        success = self.db.store_event(event)
        
        # Process event for real-time metrics
        if success and event_type in self.event_processors:
            self.event_processors[event_type](event)
        
        return success
    
    def _process_session_start(self, event: AnalyticsEvent):
        """Process session start event"""
        # Track session initiation metrics
        self.db.store_user_metric(
            metric_id=f"{event.user_id}_session_start_{int(event.timestamp)}",
            user_id=event.user_id,
            session_id=event.session_id,
            metric_type="session_engagement",
            value=1.0,
            metadata={"event": "session_started", "persona": event.data.get("persona_name")}
        )
        
        logger.debug(f"Processed session start for user {event.user_id}")
    
    def _process_session_end(self, event: AnalyticsEvent):
        """Process session end event"""
        duration = event.data.get("duration_minutes", 0)
        completion_status = event.data.get("completion_status", "unknown")
        
        # Track session completion
        self.db.store_user_metric(
            metric_id=f"{event.user_id}_session_end_{int(event.timestamp)}",
            user_id=event.user_id,
            session_id=event.session_id,
            metric_type="session_duration",
            value=duration,
            metadata={"completion_status": completion_status}
        )
        
        # Store session summary
        self.db.store_session_summary(event.data)
        
        logger.debug(f"Processed session end for user {event.user_id}: {duration} minutes")
    
    def _process_message_sent(self, event: AnalyticsEvent):
        """Process message sent event"""
        message_length = len(event.data.get("message", ""))
        response_time = event.data.get("response_time_seconds", 0)
        
        # Track engagement
        self.db.store_user_metric(
            metric_id=f"{event.user_id}_message_{int(event.timestamp)}",
            user_id=event.user_id,
            session_id=event.session_id,
            metric_type="message_engagement",
            value=message_length,
            metadata={"response_time": response_time}
        )
    
    def _process_feedback_generated(self, event: AnalyticsEvent):
        """Process feedback generation event"""
        overall_score = event.data.get("overall_score", 0)
        category_scores = event.data.get("category_scores", {})
        
        # Store overall score
        self.db.store_user_metric(
            metric_id=f"{event.user_id}_overall_score_{int(event.timestamp)}",
            user_id=event.user_id,
            session_id=event.session_id,
            metric_type="overall_performance",
            value=overall_score,
            metadata=category_scores
        )
        
        # Store individual category scores
        for category, score_data in category_scores.items():
            if isinstance(score_data, dict) and 'score' in score_data:
                self.db.store_user_metric(
                    metric_id=f"{event.user_id}_{category}_{int(event.timestamp)}",
                    user_id=event.user_id,
                    session_id=event.session_id,
                    metric_type=f"category_{category}",
                    value=score_data['score'],
                    metadata={"reasoning": score_data.get("reasoning", "")}
                )
    
    def _process_user_action(self, event: AnalyticsEvent):
        """Process user action event"""
        action_type = event.data.get("action_type", "unknown")
        
        self.db.store_user_metric(
            metric_id=f"{event.user_id}_action_{int(event.timestamp)}",
            user_id=event.user_id,
            session_id=event.session_id,
            metric_type="user_action",
            value=1.0,
            metadata={"action_type": action_type}
        )
    
    def generate_user_analytics(self, user_id: str, days_back: int = 30) -> Dict[str, Any]:
        """Generate comprehensive user analytics"""
        sessions = self.db.get_session_summaries(user_id, days_back)
        metrics = self.db.get_user_metrics(user_id, days_back=days_back)
        events = self.db.get_user_events(user_id, hours_back=days_back * 24)
        
        if not sessions and not metrics:
            return {"error": "No data available for user"}
        
        analytics = {
            "user_id": user_id,
            "time_period": f"Last {days_back} days",
            "generated_at": time.time(),
            "overview": self._generate_overview(sessions, metrics, events),
            "performance_trends": self._analyze_performance_trends(sessions, metrics),
            "engagement_metrics": self._calculate_engagement_metrics(sessions, events),
            "skill_progression": self._analyze_skill_progression(sessions, metrics),
            "learning_insights": self._generate_learning_insights(sessions, metrics),
            "recommendations": self._generate_recommendations(sessions, metrics)
        }
        
        return analytics
    
    def _generate_overview(self, sessions: List[Dict], metrics: List[Dict], 
                          events: List[Dict]) -> Dict[str, Any]:
        """Generate overview statistics"""
        if not sessions:
            return {"total_sessions": 0}
        
        total_sessions = len(sessions)
        completed_sessions = sum(1 for s in sessions if s.get('end_time'))
        total_duration = sum(s.get('duration_minutes', 0) for s in sessions)
        avg_session_duration = total_duration / max(total_sessions, 1)
        
        scores = [s.get('overall_score', 0) for s in sessions if s.get('overall_score')]
        avg_score = statistics.mean(scores) if scores else 0
        score_improvement = 0
        
        if len(scores) >= 2:
            recent_scores = scores[-3:] if len(scores) >= 3 else scores[-2:]
            early_scores = scores[:3] if len(scores) >= 3 else scores[:2]
            score_improvement = statistics.mean(recent_scores) - statistics.mean(early_scores)
        
        # Engagement metrics
        personas_practiced = len(set(s.get('persona_name', '') for s in sessions))
        total_messages = sum(s.get('messages_exchanged', 0) for s in sessions)
        
        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "completion_rate": (completed_sessions / max(total_sessions, 1)) * 100,
            "total_practice_time": round(total_duration, 1),
            "avg_session_duration": round(avg_session_duration, 1),
            "current_average_score": round(avg_score, 1),
            "score_improvement": round(score_improvement, 1),
            "personas_practiced": personas_practiced,
            "total_conversations": total_messages,
            "practice_frequency": round(total_sessions / max(1, 7), 1)  # sessions per week
        }
    
    def _analyze_performance_trends(self, sessions: List[Dict], 
                                  metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze performance trends over time"""
        if not sessions:
            return {"trend": "no_data"}
        
        # Sort sessions by time
        sorted_sessions = sorted(sessions, key=lambda x: x.get('start_time', 0))
        
        # Calculate trends for overall scores
        scores_over_time = []
        category_trends = defaultdict(list)
        
        for session in sorted_sessions:
            if session.get('overall_score'):
                scores_over_time.append({
                    "timestamp": session.get('start_time'),
                    "score": session.get('overall_score'),
                    "session_id": session.get('session_id')
                })
            
            # Category-specific trends
            category_scores = session.get('category_scores', {})
            for category, score_data in category_scores.items():
                if isinstance(score_data, dict) and 'score' in score_data:
                    category_trends[category].append({
                        "timestamp": session.get('start_time'),
                        "score": score_data['score']
                    })
        
        # Calculate trend direction
        overall_trend = "stable"
        if len(scores_over_time) >= 3:
            recent_avg = statistics.mean([s["score"] for s in scores_over_time[-3:]])
            early_avg = statistics.mean([s["score"] for s in scores_over_time[:3]])
            
            if recent_avg > early_avg + 5:
                overall_trend = "improving"
            elif recent_avg < early_avg - 5:
                overall_trend = "declining"
        
        # Category trend analysis
        category_trend_analysis = {}
        for category, scores in category_trends.items():
            if len(scores) >= 2:
                trend_slope = (scores[-1]["score"] - scores[0]["score"]) / len(scores)
                category_trend_analysis[category] = {
                    "trend_slope": round(trend_slope, 2),
                    "current_score": round(scores[-1]["score"], 1),
                    "first_score": round(scores[0]["score"], 1),
                    "total_improvement": round(scores[-1]["score"] - scores[0]["score"], 1)
                }
        
        return {
            "overall_trend": overall_trend,
            "scores_over_time": scores_over_time[-10:],  # Last 10 sessions
            "category_trends": category_trend_analysis,
            "performance_consistency": self._calculate_consistency(scores_over_time),
            "best_performing_session": max(scores_over_time, key=lambda x: x["score"]) if scores_over_time else None,
            "improvement_velocity": self._calculate_improvement_velocity(scores_over_time)
        }
    
    def _calculate_engagement_metrics(self, sessions: List[Dict], 
                                    events: List[Dict]) -> Dict[str, Any]:
        """Calculate user engagement metrics"""
        if not sessions:
            return {"engagement_level": "no_data"}
        
        # Session frequency analysis
        session_dates = [datetime.fromtimestamp(s.get('start_time', 0)).date() 
                        for s in sessions if s.get('start_time')]
        unique_days = len(set(session_dates))
        
        # Calculate streaks
        consecutive_days = self._calculate_practice_streaks(session_dates)
        
        # Message engagement
        total_messages = sum(s.get('messages_exchanged', 0) for s in sessions)
        avg_messages_per_session = total_messages / max(len(sessions), 1)
        
        # Time-based engagement
        total_time = sum(s.get('duration_minutes', 0) for s in sessions)
        avg_session_time = total_time / max(len(sessions), 1)
        
        # Engagement score calculation
        frequency_score = min(100, unique_days * 5)  # 5 points per practice day
        consistency_score = min(100, max(consecutive_days) * 10)  # 10 points per consecutive day
        depth_score = min(100, avg_messages_per_session * 5)  # 5 points per message
        duration_score = min(100, avg_session_time * 2)  # 2 points per minute
        
        overall_engagement = (frequency_score + consistency_score + depth_score + duration_score) / 4
        
        # Engagement level classification
        if overall_engagement >= 80:
            engagement_level = "highly_engaged"
        elif overall_engagement >= 60:
            engagement_level = "moderately_engaged"
        elif overall_engagement >= 40:
            engagement_level = "lightly_engaged"
        else:
            engagement_level = "disengaged"
        
        return {
            "engagement_level": engagement_level,
            "overall_engagement_score": round(overall_engagement, 1),
            "practice_frequency": {
                "unique_practice_days": unique_days,
                "sessions_per_day": round(len(sessions) / max(unique_days, 1), 1),
                "longest_streak": max(consecutive_days) if consecutive_days else 0,
                "current_streak": consecutive_days[-1] if consecutive_days else 0
            },
            "session_engagement": {
                "avg_messages_per_session": round(avg_messages_per_session, 1),
                "avg_session_duration": round(avg_session_time, 1),
                "completion_rate": sum(1 for s in sessions if s.get('end_time')) / len(sessions) * 100
            },
            "persona_diversity": {
                "unique_personas": len(set(s.get('persona_name', '') for s in sessions)),
                "most_practiced": Counter([s.get('persona_name', '') for s in sessions]).most_common(1)[0] if sessions else None
            }
        }
    
    def _calculate_practice_streaks(self, session_dates: List) -> List[int]:
        """Calculate consecutive practice day streaks"""
        if not session_dates:
            return []
        
        sorted_dates = sorted(set(session_dates))
        streaks = []
        current_streak = 1
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                current_streak += 1
            else:
                streaks.append(current_streak)
                current_streak = 1
        
        streaks.append(current_streak)
        return streaks
    
    def _analyze_skill_progression(self, sessions: List[Dict], 
                                 metrics: List[Dict]) -> Dict[str, Any]:
        """Analyze skill progression across categories"""
        if not sessions:
            return {"progression": "no_data"}
        
        # Group sessions by skill categories
        skill_progression = {}
        categories = set()
        
        for session in sessions:
            category_scores = session.get('category_scores', {})
            for category, score_data in category_scores.items():
                categories.add(category)
                if category not in skill_progression:
                    skill_progression[category] = []
                
                if isinstance(score_data, dict) and 'score' in score_data:
                    skill_progression[category].append({
                        "timestamp": session.get('start_time'),
                        "score": score_data['score'],
                        "session_id": session.get('session_id')
                    })
        
        # Analyze progression for each skill
        skill_analysis = {}
        for category, scores in skill_progression.items():
            if len(scores) >= 2:
                sorted_scores = sorted(scores, key=lambda x: x['timestamp'])
                first_score = sorted_scores[0]['score']
                latest_score = sorted_scores[-1]['score']
                improvement = latest_score - first_score
                
                # Calculate learning rate
                sessions_count = len(sorted_scores)
                learning_rate = improvement / sessions_count if sessions_count > 0 else 0
                
                # Determine mastery level
                if latest_score >= 90:
                    mastery_level = "expert"
                elif latest_score >= 75:
                    mastery_level = "proficient"
                elif latest_score >= 60:
                    mastery_level = "competent"
                elif latest_score >= 45:
                    mastery_level = "developing"
                else:
                    mastery_level = "novice"
                
                skill_analysis[category] = {
                    "current_score": round(latest_score, 1),
                    "starting_score": round(first_score, 1),
                    "total_improvement": round(improvement, 1),
                    "learning_rate": round(learning_rate, 2),
                    "sessions_practiced": sessions_count,
                    "mastery_level": mastery_level,
                    "consistency": round(statistics.stdev([s['score'] for s in sorted_scores]), 1) if len(sorted_scores) > 1 else 0
                }
        
        # Overall skill development metrics
        all_improvements = [skill['total_improvement'] for skill in skill_analysis.values()]
        avg_improvement = statistics.mean(all_improvements) if all_improvements else 0
        
        # Identify strongest and weakest skills
        strongest_skill = max(skill_analysis.items(), key=lambda x: x[1]['current_score']) if skill_analysis else None
        weakest_skill = min(skill_analysis.items(), key=lambda x: x[1]['current_score']) if skill_analysis else None
        
        return {
            "skill_breakdown": skill_analysis,
            "overall_improvement": round(avg_improvement, 1),
            "strongest_skill": strongest_skill[0] if strongest_skill else None,
            "weakest_skill": weakest_skill[0] if weakest_skill else None,
            "skills_improving": sum(1 for skill in skill_analysis.values() if skill['total_improvement'] > 0),
            "skills_declining": sum(1 for skill in skill_analysis.values() if skill['total_improvement'] < 0),
            "learning_velocity": round(statistics.mean([skill['learning_rate'] for skill in skill_analysis.values()]), 2) if skill_analysis else 0
        }
    
    def _calculate_consistency(self, scores_over_time: List[Dict]) -> Dict[str, Any]:
        """Calculate performance consistency metrics"""
        if len(scores_over_time) < 3:
            return {"consistency_score": 0, "volatility": "insufficient_data"}
        
        scores = [s["score"] for s in scores_over_time]
        std_dev = statistics.stdev(scores)
        mean_score = statistics.mean(scores)
        
        # Coefficient of variation (lower is more consistent)
        cv = (std_dev / mean_score) * 100 if mean_score > 0 else 100
        
        # Consistency score (0-100, higher is better)
        consistency_score = max(0, 100 - cv)
        
        # Volatility classification
        if cv < 10:
            volatility = "very_consistent"
        elif cv < 20:
            volatility = "consistent"
        elif cv < 30:
            volatility = "moderately_variable"
        else:
            volatility = "highly_variable"
        
        return {
            "consistency_score": round(consistency_score, 1),
            "standard_deviation": round(std_dev, 1),
            "coefficient_of_variation": round(cv, 1),
            "volatility": volatility
        }
    
    def _calculate_improvement_velocity(self, scores_over_time: List[Dict]) -> float:
        """Calculate rate of improvement over time"""
        if len(scores_over_time) < 2:
            return 0.0
        
        # Calculate linear regression slope
        n = len(scores_over_time)
        x_values = list(range(n))
        y_values = [s["score"] for s in scores_over_time]
        
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        slope = numerator / denominator if denominator != 0 else 0
        return round(slope, 3)
    
    def _generate_learning_insights(self, sessions: List[Dict], 
                                   metrics: List[Dict]) -> Dict[str, Any]:
        """Generate learning insights and patterns"""
        if not sessions:
            return {"insights": []}
        
        insights = []
        
        # Time of day analysis
        session_hours = [datetime.fromtimestamp(s.get('start_time', 0)).hour 
                        for s in sessions if s.get('start_time')]
        
        if session_hours:
            peak_hour = Counter(session_hours).most_common(1)[0][0]
            insights.append(f"Most productive practice time: {peak_hour}:00-{peak_hour+1}:00")
        
        # Session duration analysis
        durations = [s.get('duration_minutes', 0) for s in sessions if s.get('duration_minutes')]
        if durations:
            avg_duration = statistics.mean(durations)
            if avg_duration < 10:
                insights.append("Consider longer practice sessions (15-20 minutes) for better learning retention")
            elif avg_duration > 30:
                insights.append("Great session length! Extended practice sessions show strong commitment")
        
        # Performance vs session frequency
        if len(sessions) >= 5:
            recent_sessions = sessions[-5:]
            recent_scores = [s.get('overall_score', 0) for s in recent_sessions if s.get('overall_score')]
            
            if recent_scores:
                recent_avg = statistics.mean(recent_scores)
                overall_scores = [s.get('overall_score', 0) for s in sessions if s.get('overall_score')]
                overall_avg = statistics.mean(overall_scores) if overall_scores else 0
                
                if recent_avg > overall_avg + 5:
                    insights.append("Recent performance shows significant improvement - keep up the momentum!")
                elif recent_avg < overall_avg - 5:
                    insights.append("Recent performance dip detected - consider reviewing fundamentals")
        
        # Persona preference analysis
        persona_performance = defaultdict(list)
        for session in sessions:
            persona = session.get('persona_name')
            score = session.get('overall_score')
            if persona and score:
                persona_performance[persona].append(score)
        
        if persona_performance:
            best_persona = max(persona_performance.items(), 
                              key=lambda x: statistics.mean(x[1]))[0]
            insights.append(f"Strongest performance with {best_persona} persona")
        
        # Feedback pattern analysis
        improvement_areas = defaultdict(int)
        for session in sessions:
            feedback_items = session.get('feedback_items', [])
            for item in feedback_items:
                if isinstance(item, dict):
                    category = item.get('category', 'unknown')
                    if item.get('feedback_type') in ['constructive', 'critical']:
                        improvement_areas[category] += 1
        
        if improvement_areas:
            most_common_issue = max(improvement_areas.items(), key=lambda x: x[1])[0]
            insights.append(f"Focus area: {most_common_issue.replace('_', ' ').title()}")
        
        return {
            "insights": insights,
            "learning_patterns": {
                "peak_practice_hour": Counter(session_hours).most_common(1)[0] if session_hours else None,
                "preferred_session_length": round(statistics.mean(durations), 1) if durations else 0,
                "best_performing_persona": max(persona_performance.items(), 
                                              key=lambda x: statistics.mean(x[1]))[0] if persona_performance else None
            },
            "improvement_focus": dict(improvement_areas)
        }
    
    def _generate_recommendations(self, sessions: List[Dict], 
                                 metrics: List[Dict]) -> List[str]:
        """Generate actionable recommendations"""
        if not sessions:
            return ["Start practicing to get personalized recommendations"]
        
        recommendations = []
        
        # Analyze recent performance
        recent_sessions = sessions[-3:] if len(sessions) >= 3 else sessions
        recent_scores = [s.get('overall_score', 0) for s in recent_sessions if s.get('overall_score')]
        
        if recent_scores:
            avg_recent_score = statistics.mean(recent_scores)
            
            if avg_recent_score < 60:
                recommendations.append("Focus on fundamental sales skills - practice basic conversation flow")
            elif avg_recent_score < 75:
                recommendations.append("Work on specific skill areas identified in feedback")
            else:
                recommendations.append("Excellent progress! Try advanced scenarios and challenging personas")
        
        # Session frequency recommendations
        if len(sessions) < 5:
            recommendations.append("Increase practice frequency to 3-4 sessions per week for faster improvement")
        
        # Persona diversity recommendations
        personas_used = set(s.get('persona_name', '') for s in sessions)
        if len(personas_used) < 3:
            recommendations.append("Practice with different persona types to build versatility")
        
        # Skill-specific recommendations
        skill_scores = defaultdict(list)
        for session in sessions:
            category_scores = session.get('category_scores', {})
            for category, score_data in category_scores.items():
                if isinstance(score_data, dict) and 'score' in score_data:
                    skill_scores[category].append(score_data['score'])
        
        for category, scores in skill_scores.items():
            avg_score = statistics.mean(scores)
            if avg_score < 65:
                category_name = category.replace('_', ' ').title()
                recommendations.append(f"Improve {category_name} skills through targeted practice")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def generate_system_analytics(self, days_back: int = 7) -> Dict[str, Any]:
        """Generate system-wide analytics"""
        all_sessions = self.db.get_session_summaries(days_back=days_back)
        
        if not all_sessions:
            return {"message": "No system data available"}
        
        # System overview
        total_users = len(set(s.get('user_id') for s in all_sessions))
        total_sessions = len(all_sessions)
        completed_sessions = sum(1 for s in all_sessions if s.get('end_time'))
        
        # Performance metrics
        all_scores = [s.get('overall_score', 0) for s in all_sessions if s.get('overall_score')]
        avg_system_score = statistics.mean(all_scores) if all_scores else 0
        
        # Usage patterns
        session_hours = [datetime.fromtimestamp(s.get('start_time', 0)).hour 
                        for s in all_sessions if s.get('start_time')]
        peak_hours = Counter(session_hours).most_common(3)
        
        # Persona usage
        persona_usage = Counter(s.get('persona_name', '') for s in all_sessions)
        
        return {
            "system_overview": {
                "total_users": total_users,
                "total_sessions": total_sessions,
                "completion_rate": (completed_sessions / max(total_sessions, 1)) * 100,
                "average_score": round(avg_system_score, 1),
                "total_practice_time": sum(s.get('duration_minutes', 0) for s in all_sessions)
            },
            "usage_patterns": {
                "peak_usage_hours": [{"hour": f"{hour}:00", "sessions": count} 
                                   for hour, count in peak_hours],
                "most_popular_personas": [{"persona": persona, "sessions": count} 
                                        for persona, count in persona_usage.most_common(5)]
            },
            "performance_distribution": self._analyze_score_distribution(all_scores),
            "engagement_metrics": {
                "active_users_today": len(set(s.get('user_id') for s in all_sessions 
                                            if s.get('start_time', 0) > time.time() - 86400)),
                "avg_sessions_per_user": round(total_sessions / max(total_users, 1), 1)
            }
        }
    
    def _analyze_score_distribution(self, scores: List[float]) -> Dict[str, Any]:
        """Analyze score distribution across users"""
        if not scores:
            return {"distribution": "no_data"}
        
        # Score ranges
        ranges = {
            "excellent": (90, 100),
            "good": (75, 89),
            "satisfactory": (60, 74),
            "needs_improvement": (0, 59)
        }
        
        distribution = {}
        for category, (min_score, max_score) in ranges.items():
            count = sum(1 for score in scores if min_score <= score <= max_score)
            distribution[category] = {
                "count": count,
                "percentage": round((count / len(scores)) * 100, 1)
            }
        
        return {
            "distribution": distribution,
            "average_score": round(statistics.mean(scores), 1),
            "median_score": round(statistics.median(scores), 1),
            "score_range": {
                "min": round(min(scores), 1),
                "max": round(max(scores), 1)
            }
        }


# Global analytics aggregator instance
analytics_aggregator = AnalyticsAggregator()

def get_analytics_aggregator() -> AnalyticsAggregator:
    """Get singleton AnalyticsAggregator instance"""
    return analytics_aggregator