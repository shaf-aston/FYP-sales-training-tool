"""
Database helper: provides a SQLAlchemy engine/session based on DATABASE_URL.
Falls back to SQLite files in data/ if env not set.
"""
import os
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from config.settings import DATA_DIR


def _default_sqlite_url() -> str:
    db_path = Path(DATA_DIR) / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


DATABASE_URL = os.environ.get("DATABASE_URL", _default_sqlite_url())
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def health_check() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "url": DATABASE_URL}
    except Exception as e:
        return {"ok": False, "error": str(e), "url": DATABASE_URL}
