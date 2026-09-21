"""Database engine, session factory, and dependencies."""

from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.base import Base

_settings = get_settings()
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    """Lazy-create the engine on first access."""
    global _engine, _SessionLocal
    if _engine is None:
        if not _settings.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. "
                "Please configure it in your .env file or environment."
            )
        # SQLite needs check_same_thread=False; pool settings only for non-SQLite
        is_sqlite = _settings.DATABASE_URL.startswith("sqlite")
        engine_kwargs: dict = {
            "echo": _settings.DEBUG,
        }
        if is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs.update({
                "pool_pre_ping": True,
                "pool_size": 5,
                "max_overflow": 10,
            })
        _engine = create_engine(_settings.DATABASE_URL, **engine_kwargs)
        _SessionLocal = sessionmaker(
            bind=_engine, autocommit=False, autoflush=False
        )
    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session."""
    engine = _get_engine()
    session_factory = sessionmaker(
        bind=engine, autocommit=False, autoflush=False
    )
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    """Check if the database is reachable."""
    try:
        engine = _get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
