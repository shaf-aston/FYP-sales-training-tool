import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict

DATABASE_URL = os.getenv("DATABASE_URL")

CREATE_PERSONAS_TABLE = """
CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    type TEXT,
    difficulty TEXT,
    background TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
"""

CREATE_ANALYTICS_TABLE = """
CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,
    user_id TEXT,
    event_type TEXT,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
"""


def _get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """Initialize DB tables if DATABASE_URL is configured."""
    if not DATABASE_URL:
        return False
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(CREATE_PERSONAS_TABLE)
        cur.execute(CREATE_ANALYTICS_TABLE)
        conn.commit()
        cur.close()
        return True
    finally:
        conn.close()


def add_persona(persona: Dict) -> Optional[Dict]:
    """Insert or update a persona. persona should contain name, type, difficulty, background, metadata."""
    if not DATABASE_URL:
        return None
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO personas (name, type, difficulty, background, metadata)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
              type = EXCLUDED.type,
              difficulty = EXCLUDED.difficulty,
              background = EXCLUDED.background,
              metadata = EXCLUDED.metadata
            RETURNING *;
            """,
            (
                persona.get("name"),
                persona.get("type"),
                persona.get("difficulty"),
                persona.get("background"),
                json.dumps(persona.get("metadata") or {}),
            ),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        return dict(row) if row else None
    finally:
        conn.close()


def get_personas() -> List[Dict]:
    if not DATABASE_URL:
        return []
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM personas ORDER BY name;")
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_persona_by_name(name: str) -> Optional[Dict]:
    if not DATABASE_URL:
        return None
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM personas WHERE name = %s LIMIT 1;", (name,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        conn.close()
