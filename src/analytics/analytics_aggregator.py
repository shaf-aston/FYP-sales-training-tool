"""
Analytics Aggregator Service
Computes dashboard metrics from analytics_events table and logs
"""
import json
import os
import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DB_AVAILABLE = False
_get_conn = None
DATABASE_URL = None
try:
    import importlib
    try:
        mod = importlib.import_module("services.ai_services.persona_db_service")
    except Exception:
        mod = importlib.import_module("src.services.ai_services.persona_db_service") if importlib.util.find_spec("src.services.ai_services.persona_db_service") else None

    if mod:
        _get_conn = getattr(mod, "_get_conn", None)
        DATABASE_URL = getattr(mod, "DATABASE_URL", None)
        if _get_conn:
            DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "conversation_events.log"


class AnalyticsAggregator:
    """Aggregates analytics from both file logs and database"""
    
    def __init__(self):
        self.skills_map = {
            'rapport_building': 'RAPPORT BUILDING',
            'objection_handling': 'OBJECTION HANDLING', 
            'closing_techniques': 'CLOSING TECHNIQUES',
            'product_knowledge': 'PRODUCT KNOWLEDGE',
            'listening_skills': 'LISTENING SKILLS',
            'persuasion_skills': 'PERSUASION SKILLS',
            'time_management': 'TIME MANAGEMENT'
        }
    
    def get_user_dashboard_metrics(self, user_id: str, days_back: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard metrics for a user"""
        try:
            if DB_AVAILABLE and DATABASE_URL:
                return self._get_metrics_from_db(user_id, days_back)
            else:
                return self._get_metrics_from_logs(user_id, days_back)
        except Exception as e:
            logger.error(f"Error computing dashboard metrics: {e}")
            return self._get_fallback_metrics(user_id)
    
    def _get_metrics_from_db(self, user_id: str, days_back: int) -> Dict[str, Any]:
        """Compute metrics from database analytics_events"""
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cutoff_date = datetime.now(UTC) - timedelta(days=days_back)
            
            cur.execute("""
                SELECT event_type, payload, created_at
                FROM analytics_events 
                WHERE user_id = %s AND created_at >= %s
                ORDER BY created_at
            """, (user_id, cutoff_date))
            
            events = cur.fetchall()
            cur.close()
            
            sessions = []
            current_session = None
            total_messages = 0
            
            for event_type, payload_json, created_at in events:
                payload = json.loads(payload_json) if payload_json else {}
                
                if event_type == 'session_started':
                    current_session = {
                        'session_id': payload.get('session_id'),
                        'persona': payload.get('persona'),
                        'start_time': created_at,
                        'messages': 0,
                        'end_time': None,
                        'success_rating': None
                    }
                    
                elif event_type == 'message_exchanged' and current_session:
                    current_session['messages'] += 1
                    total_messages += 1
                    
                elif event_type == 'session_ended' and current_session:
                    current_session['end_time'] = created_at
                    current_session['success_rating'] = payload.get('success_rating', 5)
                    sessions.append(current_session)
                    current_session = None
            
            if current_session:
                sessions.append(current_session)
            
            return self._compute_metrics_from_sessions(user_id, sessions, total_messages)
            
        finally:
            conn.close()
    
    def _get_metrics_from_logs(self, user_id: str, days_back: int) -> Dict[str, Any]:
        """Compute metrics from log files"""
        if not LOG_FILE.exists():
            return self._get_fallback_metrics(user_id)
        
        cutoff_date = datetime.now(UTC) - timedelta(days=days_back)
        sessions = []
        current_session = None
        total_messages = 0
        
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        event = entry.get('event', {})
                        
                        if event.get('user_id') != user_id:
                            continue
                        
                        event_time = datetime.fromisoformat(entry['ts'].replace('Z', '+00:00'))
                        if event_time < cutoff_date:
                            continue
                        
                        event_type = event.get('event_type')
                        payload = event.get('payload', {})
                        
                        if event_type == 'session_started':
                            current_session = {
                                'session_id': payload.get('session_id'),
                                'persona': payload.get('persona'),
                                'start_time': event_time,
                                'messages': 0,
                                'end_time': None,
                                'success_rating': None
                            }
                            
                        elif event_type == 'message_exchanged' and current_session:
                            current_session['messages'] += 1
                            total_messages += 1
                            
                        elif event_type == 'session_ended' and current_session:
                            current_session['end_time'] = event_time
                            current_session['success_rating'] = payload.get('success_rating', 5)
                            sessions.append(current_session)
                            current_session = None
                            
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(f"Skipping malformed log entry: {e}")
                        continue
            
            if current_session:
                sessions.append(current_session)
            
            return self._compute_metrics_from_sessions(user_id, sessions, total_messages)
            
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
            return self._get_fallback_metrics(user_id)
    
    def _compute_metrics_from_sessions(self, user_id: str, sessions: List[Dict], total_messages: int) -> Dict[str, Any]:
        """Compute final dashboard metrics from session data"""
        
        total_sessions = len(sessions)
        completed_sessions = [s for s in sessions if s.get('end_time')]
        
        total_hours = 0.0
        for session in completed_sessions:
            if session['start_time'] and session['end_time']:
                duration = session['end_time'] - session['start_time']
                total_hours += duration.total_seconds() / 3600
        
        ratings = [s['success_rating'] for s in completed_sessions if s.get('success_rating')]
        avg_rating = sum(ratings) / len(ratings) if ratings else 5.0
        
        skills_progress = self._compute_skill_progress(sessions, total_messages)
        
        avg_skill_progress = sum(skill['progress_percentage'] for skill in skills_progress.values()) / len(skills_progress)
        
        return {
            "user_profile": {
                "user_id": user_id,
                "experience_level": "beginner",
                "training_style": "guided"
            },
            "overall_progress": {
                "completion_percentage": round(avg_skill_progress, 1),
                "skills_mastered": len([s for s in skills_progress.values() if s['progress_percentage'] >= 80])
            },
            "session_statistics": {
                "total_sessions": total_sessions,
                "completed_sessions": len(completed_sessions),
                "total_hours": round(total_hours, 1),
                "average_success_rating": round(avg_rating, 1),
                "total_messages": total_messages
            },
            "skills_breakdown": skills_progress,
            "recent_activity": {
                "last_session": sessions[-1]['start_time'].isoformat() if sessions else None,
                "sessions_this_week": len([s for s in sessions if s['start_time'] > datetime.utcnow() - timedelta(days=7)]),
                "most_used_persona": self._get_most_used_persona(sessions)
            },
            "next_recommendations": [
                "Practice with Jake for objection handling",
                "Focus on closing techniques with Mary",
                "Work on time management scenarios"
            ]
        }
    
    def _compute_skill_progress(self, sessions: List[Dict], total_messages: int) -> Dict[str, Any]:
        """Compute skill progress based on session activity"""
        base_progress = {
            'rapport_building': 50.0,
            'objection_handling': 50.0, 
            'closing_techniques': 66.7,
            'product_knowledge': 20.0,
            'listening_skills': 40.0,
            'persuasion_skills': 50.0,
            'time_management': 40.0
        }
        
        activity_boost = min(total_messages * 2, 30)
        
        skills_breakdown = {}
        for skill_key, base_pct in base_progress.items():
            adjusted_pct = min(base_pct + activity_boost, 100)
            
            if adjusted_pct < 40:
                current_level = "beginner"
                target_level = "intermediate"
            elif adjusted_pct < 80:
                current_level = "intermediate" if adjusted_pct >= 60 else "beginner"
                target_level = "advanced" if current_level == "intermediate" else "intermediate"
            else:
                current_level = "advanced"
                target_level = "expert"
            
            skills_breakdown[skill_key] = {
                "current_level": current_level,
                "target_level": target_level,
                "progress_percentage": round(adjusted_pct, 1)
            }
        
        return skills_breakdown
    
    def _get_most_used_persona(self, sessions: List[Dict]) -> Optional[str]:
        """Get the most frequently used persona"""
        if not sessions:
            return None
        
        persona_counts = {}
        for session in sessions:
            persona = session.get('persona')
            if persona:
                persona_counts[persona] = persona_counts.get(persona, 0) + 1
        
        if not persona_counts:
            return None
        
        return max(persona_counts, key=persona_counts.get)
    
    def _get_fallback_metrics(self, user_id: str) -> Dict[str, Any]:
        """Return fallback metrics when no data is available"""
        return {
            "user_profile": {
                "user_id": user_id,
                "experience_level": "beginner",
                "training_style": "guided"
            },
            "overall_progress": {
                "completion_percentage": 0.0,
                "skills_mastered": 0
            },
            "session_statistics": {
                "total_sessions": 0,
                "completed_sessions": 0,
                "total_hours": 0.0,
                "average_success_rating": 0.0,
                "total_messages": 0
            },
            "skills_breakdown": {
                skill_key: {
                    "current_level": "beginner",
                    "target_level": "intermediate", 
                    "progress_percentage": 0.0
                }
                for skill_key in self.skills_map.keys()
            },
            "recent_activity": {
                "last_session": None,
                "sessions_this_week": 0,
                "most_used_persona": None
            },
            "next_recommendations": [
                "Complete your first training session",
                "Try different personas to explore various scenarios",
                "Set learning goals for focused improvement"
            ]
        }
    
    def get_system_analytics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get system-wide analytics"""
        try:
            if DB_AVAILABLE and DATABASE_URL:
                return self._get_system_analytics_from_db(days_back)
            else:
                return self._get_system_analytics_from_logs(days_back)
        except Exception as e:
            logger.error(f"Error getting system analytics: {e}")
            return {"error": "Failed to compute system analytics"}
    
    def _get_system_analytics_from_db(self, days_back: int) -> Dict[str, Any]:
        """Get system analytics from database"""
        conn = _get_conn()
        try:
            cur = conn.cursor()
            cutoff_date = datetime.now(UTC) - timedelta(days=days_back)
            
            cur.execute("SELECT COUNT(*) FROM analytics_events WHERE created_at >= %s", (cutoff_date,))
            total_events = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM analytics_events WHERE created_at >= %s", (cutoff_date,))
            unique_users = cur.fetchone()[0]
            
            cur.execute("""
                SELECT event_type, COUNT(*) 
                FROM analytics_events 
                WHERE created_at >= %s 
                GROUP BY event_type
            """, (cutoff_date,))
            event_breakdown = dict(cur.fetchall())
            
            cur.close()
            
            return {
                "timeframe_days": days_back,
                "total_events": total_events,
                "unique_users": unique_users,
                "event_breakdown": event_breakdown,
                "computed_at": datetime.now(UTC).isoformat()
            }
            
        finally:
            conn.close()
    
    def _get_system_analytics_from_logs(self, days_back: int) -> Dict[str, Any]:
        """Get system analytics from log files"""
        if not LOG_FILE.exists():
            return {"error": "No log file found"}
        
        cutoff_date = datetime.now(UTC) - timedelta(days=days_back)
        total_events = 0
        unique_users = set()
        event_breakdown = {}
        
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        event = entry.get('event', {})
                        
                        event_time = datetime.fromisoformat(entry['ts'].replace('Z', '+00:00'))
                        if event_time < cutoff_date:
                            continue
                        
                        total_events += 1
                        unique_users.add(event.get('user_id'))
                        
                        event_type = event.get('event_type', 'unknown')
                        event_breakdown[event_type] = event_breakdown.get(event_type, 0) + 1
                        
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            
            return {
                "timeframe_days": days_back,
                "total_events": total_events,
                "unique_users": len(unique_users),
                "event_breakdown": event_breakdown,
                "computed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error reading system analytics from logs: {e}")
            return {"error": "Failed to read analytics logs"}


analytics_aggregator = AnalyticsAggregator()