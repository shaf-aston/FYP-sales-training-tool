# PostgreSQL Migration Plan

This project currently stores session and quality data in SQLite for simplicity. This guide outlines a clear path to PostgreSQL.

## Configuration
- Provide `DATABASE_URL` env var, e.g.: `postgresql+psycopg2://user:pass@host:5432/dbname`.
- If absent, the app falls back to SQLite at `data/app.db`.
- Utility: `utils/db.py` exposes `engine`, `SessionLocal`, and `health_check()`.

## Tables (minimal starting point)
- sessions (id, user_id, persona_name, started_at, ended_at, messages_json)
- quality_metrics (id, session_id, metric, value, created_at)

## Steps
1. Provision Postgres and set `DATABASE_URL`.
2. Create tables (SQL or Alembic). Example DDL provided in `migrations/`.
3. Update services to persist:
   - `ChatService`: write session metadata on start/end.
   - Feedback: store aggregated metrics per session.
4. Migrate existing SQLite data (optional):
   - Export to CSV/JSON and import into Postgres, or use a simple script.
5. CI check: add a startup health probe calling `utils.db.health_check()`.

## Notes
- Keep SQLite fallback for local dev.
- Use parameterized queries or ORM to avoid SQL injection.
