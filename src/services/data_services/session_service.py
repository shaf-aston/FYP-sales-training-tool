"""
Session Management Service - Persistent Storage for Training Sessions

This service provides comprehensive session management capabilities including:
- Training session creation and tracking
- Conversation history storage and retrieval
- Session-based performance metrics
- Multi-user session management
- Session analytics and reporting

Features:
- SQLite database for reliable persistent storage
- Full conversation logging with metadata
- Session state management (active, completed, paused)
- Performance tracking per session
- Export capabilities for session data
- Search and filtering for session history
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

@dataclass
class ConversationTurn:
    """Represents a single turn in a conversation"""
    turn_id: str
    session_id: str
    user_message: str
    bot_response: str
    persona_used: str
    timestamp: datetime
    response_time: float
    context_tokens: int
    feedback_scores: Optional[Dict[str, float]] = None
    user_emotions: Optional[List[str]] = None
    bot_confidence: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class TrainingSession:
    """Represents a complete training session"""
    session_id: str
    user_id: str
    persona_id: str
    session_type: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = 'active' 
    session_goals: Optional[List[str]] = None
    total_turns: int = 0
    total_duration: Optional[float] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    final_scores: Optional[Dict[str, float]] = None
    session_notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingSession':
        """Create from dictionary"""
        data['start_time'] = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)

from config.settings import SESSIONS_DB_PATH, DEFAULT_CONVERSATION_LIMIT

class SessionDatabase:
    """Database manager for session storage"""
    
    def __init__(self, db_path: str | Path = None):
        """Initialize database connection"""
        resolved = Path(db_path) if db_path else Path(SESSIONS_DB_PATH)
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
                CREATE TABLE IF NOT EXISTS training_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    persona_id TEXT NOT NULL,
                    session_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'active',
                    session_goals TEXT,  -- JSON array
                    total_turns INTEGER DEFAULT 0,
                    total_duration REAL,
                    performance_metrics TEXT,  -- JSON object
                    final_scores TEXT,  -- JSON object
                    session_notes TEXT,
                    metadata TEXT,  -- JSON object
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    persona_used TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    response_time REAL NOT NULL,
                    context_tokens INTEGER NOT NULL,
                    feedback_scores TEXT,  -- JSON object
                    user_emotions TEXT,    -- JSON array
                    bot_confidence REAL,
                    metadata TEXT,         -- JSON object
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES training_sessions (session_id)
                )
            ''')
            
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON training_sessions (user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_status ON training_sessions (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON training_sessions (start_time)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_turns_session_id ON conversation_turns (session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON conversation_turns (timestamp)')
            
            logger.info("Session database initialized successfully")

    def create_session(self, session: TrainingSession) -> bool:
        """Create a new training session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO training_sessions (
                        session_id, user_id, persona_id, session_type,
                        start_time, status, session_goals, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    session.session_id,
                    session.user_id,
                    session.persona_id,
                    session.session_type,
                    session.start_time.isoformat(),
                    session.status,
                    json.dumps(session.session_goals) if session.session_goals else None,
                    json.dumps(session.metadata) if session.metadata else None
                ))
                logger.info(f"Created session {session.session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False

    def add_conversation_turn(self, turn: ConversationTurn) -> bool:
        """Add a conversation turn to the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversation_turns (
                        turn_id, session_id, user_message, bot_response,
                        persona_used, timestamp, response_time, context_tokens,
                        feedback_scores, user_emotions, bot_confidence, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    turn.turn_id,
                    turn.session_id,
                    turn.user_message,
                    turn.bot_response,
                    turn.persona_used,
                    turn.timestamp.isoformat(),
                    turn.response_time,
                    turn.context_tokens,
                    json.dumps(turn.feedback_scores) if turn.feedback_scores else None,
                    json.dumps(turn.user_emotions) if turn.user_emotions else None,
                    turn.bot_confidence,
                    json.dumps(turn.metadata) if turn.metadata else None
                ))
                
                cursor.execute('''
                    UPDATE training_sessions 
                    SET total_turns = total_turns + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                ''', (turn.session_id,))
                
                logger.debug(f"Added turn {turn.turn_id} to session {turn.session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to add conversation turn: {e}")
            return False

    def complete_session(self, session_id: str, 
                        performance_metrics: Optional[Dict[str, Any]] = None,
                        final_scores: Optional[Dict[str, float]] = None,
                        session_notes: Optional[str] = None) -> bool:
        """Mark a session as completed with final metrics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                end_time = datetime.now()
                
                cursor.execute('SELECT start_time FROM training_sessions WHERE session_id = ?', (session_id,))
                row = cursor.fetchone()
                if not row:
                    logger.error(f"Session {session_id} not found")
                    return False
                
                start_time = datetime.fromisoformat(row['start_time'])
                duration = (end_time - start_time).total_seconds()
                
                cursor.execute('''
                    UPDATE training_sessions 
                    SET status = 'completed',
                        end_time = ?,
                        total_duration = ?,
                        performance_metrics = ?,
                        final_scores = ?,
                        session_notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                ''', (
                    end_time.isoformat(),
                    duration,
                    json.dumps(performance_metrics) if performance_metrics else None,
                    json.dumps(final_scores) if final_scores else None,
                    session_notes,
                    session_id
                ))
                
                logger.info(f"Completed session {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to complete session: {e}")
            return False

    def get_session(self, session_id: str) -> Optional[TrainingSession]:
        """Retrieve a session by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM training_sessions WHERE session_id = ?', (session_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                session_data = {
                    'session_id': row['session_id'],
                    'user_id': row['user_id'],
                    'persona_id': row['persona_id'],
                    'session_type': row['session_type'],
                    'start_time': datetime.fromisoformat(row['start_time']),
                    'end_time': datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                    'status': row['status'],
                    'session_goals': json.loads(row['session_goals']) if row['session_goals'] else None,
                    'total_turns': row['total_turns'],
                    'total_duration': row['total_duration'],
                    'performance_metrics': json.loads(row['performance_metrics']) if row['performance_metrics'] else None,
                    'final_scores': json.loads(row['final_scores']) if row['final_scores'] else None,
                    'session_notes': row['session_notes'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                }
                
                return TrainingSession(**session_data)
        except Exception as e:
            logger.error(f"Failed to get session: {e}")
            return None

    def get_session_conversation(self, session_id: str, limit: Optional[int] = None) -> List[ConversationTurn]:
        """Get all conversation turns for a session, optionally limited by the most recent turns"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT * FROM conversation_turns 
                    WHERE session_id = ? 
                    ORDER BY timestamp ASC
                """
                params = [session_id]
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                cursor.execute(query, params)
                
                turns = []
                for row in cursor.fetchall():
                    turn_data = {
                        'turn_id': row['turn_id'],
                        'session_id': row['session_id'],
                        'user_message': row['user_message'],
                        'bot_response': row['bot_response'],
                        'persona_used': row['persona_used'],
                        'timestamp': datetime.fromisoformat(row['timestamp']),
                        'response_time': row['response_time'],
                        'context_tokens': row['context_tokens'],
                        'feedback_scores': json.loads(row['feedback_scores']) if row['feedback_scores'] else None,
                        'user_emotions': json.loads(row['user_emotions']) if row['user_emotions'] else None,
                        'bot_confidence': row['bot_confidence'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else None
                    }
                    turns.append(ConversationTurn(**turn_data))
                
                return turns
        except Exception as e:
            logger.error(f"Failed to get session conversation: {e}")
            return []

    def get_user_sessions(self, user_id: str, 
                         status: Optional[str] = None,
                         limit: int = 50,
                         offset: int = 0) -> List[TrainingSession]:
        """Get sessions for a specific user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT * FROM training_sessions WHERE user_id = ?'
                params = [user_id]
                
                if status:
                    query += ' AND status = ?'
                    params.append(status)
                
                query += ' ORDER BY start_time DESC LIMIT ? OFFSET ?'
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                
                sessions = []
                for row in cursor.fetchall():
                    session_data = {
                        'session_id': row['session_id'],
                        'user_id': row['user_id'],
                        'persona_id': row['persona_id'],
                        'session_type': row['session_type'],
                        'start_time': datetime.fromisoformat(row['start_time']),
                        'end_time': datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                        'status': row['status'],
                        'session_goals': json.loads(row['session_goals']) if row['session_goals'] else None,
                        'total_turns': row['total_turns'],
                        'total_duration': row['total_duration'],
                        'performance_metrics': json.loads(row['performance_metrics']) if row['performance_metrics'] else None,
                        'final_scores': json.loads(row['final_scores']) if row['final_scores'] else None,
                        'session_notes': row['session_notes'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else None
                    }
                    sessions.append(TrainingSession(**session_data))
                
                return sessions
        except Exception as e:
            logger.error(f"Failed to get user sessions: {e}")
            return []

    def search_sessions(self, 
                       user_id: Optional[str] = None,
                       persona_id: Optional[str] = None,
                       session_type: Optional[str] = None,
                       status: Optional[str] = None,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None,
                       limit: int = 100) -> List[TrainingSession]:
        """Search sessions with various filters"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = 'SELECT * FROM training_sessions WHERE 1=1'
                params = []
                
                if user_id:
                    query += ' AND user_id = ?'
                    params.append(user_id)
                
                if persona_id:
                    query += ' AND persona_id = ?'
                    params.append(persona_id)
                
                if session_type:
                    query += ' AND session_type = ?'
                    params.append(session_type)
                
                if status:
                    query += ' AND status = ?'
                    params.append(status)
                
                if start_date:
                    query += ' AND start_time >= ?'
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += ' AND start_time <= ?'
                    params.append(end_date.isoformat())
                
                query += ' ORDER BY start_time DESC LIMIT ?'
                params.append(limit)
                
                cursor.execute(query, params)
                
                sessions = []
                for row in cursor.fetchall():
                    session_data = {
                        'session_id': row['session_id'],
                        'user_id': row['user_id'],
                        'persona_id': row['persona_id'],
                        'session_type': row['session_type'],
                        'start_time': datetime.fromisoformat(row['start_time']),
                        'end_time': datetime.fromisoformat(row['end_time']) if row['end_time'] else None,
                        'status': row['status'],
                        'session_goals': json.loads(row['session_goals']) if row['session_goals'] else None,
                        'total_turns': row['total_turns'],
                        'total_duration': row['total_duration'],
                        'performance_metrics': json.loads(row['performance_metrics']) if row['performance_metrics'] else None,
                        'final_scores': json.loads(row['final_scores']) if row['final_scores'] else None,
                        'session_notes': row['session_notes'],
                        'metadata': json.loads(row['metadata']) if row['metadata'] else None
                    }
                    sessions.append(TrainingSession(**session_data))
                
                return sessions
        except Exception as e:
            logger.error(f"Failed to search sessions: {e}")
            return []

    def get_session_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive session statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                base_session_query = 'SELECT * FROM training_sessions'
                base_turn_query = 'SELECT * FROM conversation_turns'
                params = []
                
                if user_id:
                    base_session_query += ' WHERE user_id = ?'
                    base_turn_query += ' WHERE session_id IN (SELECT session_id FROM training_sessions WHERE user_id = ?)'
                    params = [user_id, user_id]
                
                cursor.execute(f'''
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_sessions,
                        AVG(total_duration) as avg_session_duration,
                        AVG(total_turns) as avg_turns_per_session,
                        MIN(start_time) as first_session,
                        MAX(start_time) as last_session
                    FROM ({base_session_query})
                ''', params)
                
                session_stats = cursor.fetchone()
                
                if user_id:
                    cursor.execute('''
                        SELECT 
                            COUNT(*) as total_turns,
                            AVG(response_time) as avg_response_time,
                            AVG(context_tokens) as avg_context_tokens
                        FROM conversation_turns 
                        WHERE session_id IN (SELECT session_id FROM training_sessions WHERE user_id = ?)
                    ''', [user_id])
                else:
                    cursor.execute('''
                        SELECT 
                            COUNT(*) as total_turns,
                            AVG(response_time) as avg_response_time,
                            AVG(context_tokens) as avg_context_tokens
                        FROM conversation_turns
                    ''')
                
                turn_stats = cursor.fetchone()
                
                session_type_query = f'''
                    SELECT session_type, COUNT(*) as count 
                    FROM ({base_session_query})
                    GROUP BY session_type
                '''
                cursor.execute(session_type_query, params)
                session_types = {row['session_type']: row['count'] for row in cursor.fetchall()}
                
                return {
                    'total_sessions': session_stats['total_sessions'] or 0,
                    'completed_sessions': session_stats['completed_sessions'] or 0,
                    'active_sessions': session_stats['active_sessions'] or 0,
                    'avg_session_duration': session_stats['avg_session_duration'] or 0,
                    'avg_turns_per_session': session_stats['avg_turns_per_session'] or 0,
                    'first_session': session_stats['first_session'],
                    'last_session': session_stats['last_session'],
                    'total_turns': turn_stats['total_turns'] or 0,
                    'avg_response_time': turn_stats['avg_response_time'] or 0,
                    'avg_context_tokens': turn_stats['avg_context_tokens'] or 0,
                    'session_type_distribution': session_types
                }
        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {}

class SessionLogStore:
    """
    High-level session management service providing comprehensive
    session logging, tracking, and analytics capabilities
    """
    
    def __init__(self, db_path: str | Path = None):
        """Initialize the session log store"""
        self.db = SessionDatabase(db_path)
        logger.info("Session Log Store initialized")

    def start_session(self, 
                     user_id: str,
                     persona_id: str,
                     session_type: str = "sales_training",
                     session_goals: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start a new training session"""
        session_id = str(uuid.uuid4())
        
        session = TrainingSession(
            session_id=session_id,
            user_id=user_id,
            persona_id=persona_id,
            session_type=session_type,
            start_time=datetime.now(UTC),
            session_goals=session_goals,
            metadata=metadata or {}
        )
        
        if self.db.create_session(session):
            logger.info(f"Started session {session_id} for user {user_id}")
            return session_id
        else:
            raise Exception("Failed to create session")

    def log_conversation_turn(self,
                            session_id: str,
                            user_message: str,
                            bot_response: str,
                            persona_used: str,
                            response_time: float,
                            context_tokens: int,
                            feedback_scores: Optional[Dict[str, float]] = None,
                            user_emotions: Optional[List[str]] = None,
                            bot_confidence: Optional[float] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Log a conversation turn"""
        turn_id = str(uuid.uuid4())
        
        turn = ConversationTurn(
            turn_id=turn_id,
            session_id=session_id,
            user_message=user_message,
            bot_response=bot_response,
            persona_used=persona_used,
            timestamp=datetime.now(),
            response_time=response_time,
            context_tokens=context_tokens,
            feedback_scores=feedback_scores,
            user_emotions=user_emotions,
            bot_confidence=bot_confidence,
            metadata=metadata or {}
        )
        
        return self.db.add_conversation_turn(turn)

    def end_session(self, 
                   session_id: str,
                   performance_metrics: Optional[Dict[str, Any]] = None,
                   final_scores: Optional[Dict[str, float]] = None,
                   session_notes: Optional[str] = None) -> bool:
        """End a training session"""
        return self.db.complete_session(
            session_id=session_id,
            performance_metrics=performance_metrics,
            final_scores=final_scores,
            session_notes=session_notes
        )

    def get_session_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get complete session details including conversation history"""
        session = self.db.get_session(session_id)
        if not session:
            return None
        
        conversation = self.db.get_session_conversation(session_id, limit=DEFAULT_CONVERSATION_LIMIT)
        
        return {
            'session': session.to_dict(),
            'conversation': [turn.to_dict() for turn in conversation],
            'summary': {
                'total_turns': len(conversation),
                'duration': session.total_duration,
                'status': session.status,
                'performance_metrics': session.performance_metrics,
                'final_scores': session.final_scores
            }
        }

    def get_user_history(self, 
                        user_id: str,
                        limit: int = 20,
                        include_conversations: bool = False) -> List[Dict[str, Any]]:
        """Get user's session history"""
        sessions = self.db.get_user_sessions(user_id, limit=limit)
        
        history = []
        for session in sessions:
            session_data = session.to_dict()
            
            if include_conversations:
                conversation = self.db.get_session_conversation(session.session_id, limit=DEFAULT_CONVERSATION_LIMIT)
                session_data['conversation'] = [turn.to_dict() for turn in conversation]
            
            history.append(session_data)
        
        return history

    def get_session_analytics(self, 
                            user_id: Optional[str] = None,
                            time_range: Optional[int] = None) -> Dict[str, Any]:
        """Get comprehensive session analytics"""
        stats = self.db.get_session_statistics(user_id)
        
        if time_range:
            start_date = datetime.now() - timedelta(days=time_range)
            sessions = self.db.search_sessions(
                user_id=user_id,
                start_date=start_date
            )
        else:
            sessions = self.db.search_sessions(user_id=user_id)
        
        if sessions:
            completion_rate = len([s for s in sessions if s.status == 'completed']) / len(sessions) * 100
            avg_session_score = 0
            scored_sessions = 0
            
            for session in sessions:
                if session.final_scores:
                    avg_session_score += sum(session.final_scores.values()) / len(session.final_scores)
                    scored_sessions += 1
            
            if scored_sessions > 0:
                avg_session_score /= scored_sessions
        else:
            completion_rate = 0
            avg_session_score = 0
        
        stats.update({
            'completion_rate': completion_rate,
            'average_session_score': avg_session_score,
            'recent_sessions': len(sessions)
        })
        
        return stats

    def export_session_data(self, 
                          session_id: str,
                          format: str = 'json') -> Optional[str]:
        """Export session data in specified format"""
        session_data = self.get_session_details(session_id)
        if not session_data:
            return None
        
        if format.lower() == 'json':
            return json.dumps(session_data, indent=2, default=str)
        else:
            logger.error(f"Unsupported export format: {format}")
            return None

    def cleanup_old_sessions(self, days: int = 90) -> int:
        """Clean up sessions older than specified days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT session_id FROM training_sessions 
                    WHERE start_time < ? AND status = 'completed'
                ''', (cutoff_date.isoformat(),))
                
                session_ids = [row[0] for row in cursor.fetchall()]
                
                if not session_ids:
                    return 0
                
                cursor.execute(f'''
                    DELETE FROM conversation_turns 
                    WHERE session_id IN ({','.join('?' * len(session_ids))})
                ''', session_ids)
                
                cursor.execute(f'''
                    DELETE FROM training_sessions 
                    WHERE session_id IN ({','.join('?' * len(session_ids))})
                ''', session_ids)
                
                logger.info(f"Cleaned up {len(session_ids)} old sessions")
                return len(session_ids)
                
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0

session_store = SessionLogStore()

__all__ = [
    'SessionLogStore', 
    'TrainingSession', 
    'ConversationTurn', 
    'SessionDatabase',
    'session_store'
]