from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config import settings


# ── Engine & session factory ──────────────────────────────────────────────────

@lru_cache
def get_engine():
    return create_engine(
        settings.database_url,
        echo=settings.debug_sql_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_use_lifo=settings.db_pool_use_lifo,
    )


@lru_cache
def get_sessionmaker():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


# ── Database initialisation ───────────────────────────────────────────────────

def setup_db(db: Session) -> None:
    """Create any required PostgreSQL extensions and run idempotent column migrations."""
    for ext in settings.postgres_extensions:
        db.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
    # Idempotent column additions — safe to run on every startup
    _migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50) NOT NULL DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS technician_id INTEGER REFERENCES technicians(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS delete_requested BOOLEAN NOT NULL DEFAULT FALSE",
    ]
    for sql in _migrations:
        try:
            db.execute(text(sql))
        except Exception:
            db.rollback()
    db.commit()


# ── Session helpers ───────────────────────────────────────────────────────────

@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context-manager session — commits on exit, rolls back on error."""
    session: Session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session per request."""
    db: Session = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
