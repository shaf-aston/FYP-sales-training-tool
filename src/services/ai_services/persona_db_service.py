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
    age INTEGER,
    background TEXT,
    personality_traits TEXT[],
    goals TEXT[],
    concerns TEXT[],
    objections TEXT[],
    budget_range TEXT,
    decision_style TEXT,
    expertise_level TEXT,
    persona_type TEXT,
    difficulty TEXT,
    health_considerations TEXT[],
    time_constraints TEXT[],
    preferred_communication TEXT,
    industry TEXT,
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
    """Insert or update a persona."""
    if not DATABASE_URL:
        return None
    conn = _get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            INSERT INTO personas (
                name, age, background, personality_traits, goals, concerns, 
                objections, budget_range, decision_style, expertise_level, 
                persona_type, difficulty, health_considerations, time_constraints, 
                preferred_communication, industry
            )
            VALUES (
                %(name)s, %(age)s, %(background)s, %(personality_traits)s, %(goals)s, 
                %(concerns)s, %(objections)s, %(budget_range)s, %(decision_style)s, 
                %(expertise_level)s, %(persona_type)s, %(difficulty)s, 
                %(health_considerations)s, %(time_constraints)s, 
                %(preferred_communication)s, %(industry)s
            )
            ON CONFLICT (name) DO UPDATE SET
              age = EXCLUDED.age,
              background = EXCLUDED.background,
              personality_traits = EXCLUDED.personality_traits,
              goals = EXCLUDED.goals,
              concerns = EXCLUDED.concerns,
              objections = EXCLUDED.objections,
              budget_range = EXCLUDED.budget_range,
              decision_style = EXCLUDED.decision_style,
              expertise_level = EXCLUDED.expertise_level,
              persona_type = EXCLUDED.persona_type,
              difficulty = EXCLUDED.difficulty,
              health_considerations = EXCLUDED.health_considerations,
              time_constraints = EXCLUDED.time_constraints,
              preferred_communication = EXCLUDED.preferred_communication,
              industry = EXCLUDED.industry
            RETURNING *;
            """,
            {
                "name": persona.get("name"),
                "age": persona.get("age"),
                "background": persona.get("background"),
                "personality_traits": persona.get("personality_traits"),
                "goals": persona.get("goals"),
                "concerns": persona.get("concerns"),
                "objections": persona.get("objections"),
                "budget_range": persona.get("budget_range"),
                "decision_style": persona.get("decision_style"),
                "expertise_level": persona.get("expertise_level"),
                "persona_type": persona.get("persona_type"),
                "difficulty": persona.get("difficulty"),
                "health_considerations": persona.get("health_considerations"),
                "time_constraints": persona.get("time_constraints"),
                "preferred_communication": persona.get("preferred_communication"),
                "industry": persona.get("industry"),
            },
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
