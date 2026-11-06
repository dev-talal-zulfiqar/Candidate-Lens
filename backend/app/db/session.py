import contextlib
import logging
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped database session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextlib.contextmanager
def open_background_session() -> Generator[Session, None, None]:
    """Acquires a database session for work running in a FastAPI
    BackgroundTask, after the request's own session has already closed.

    A dedicated seam rather than calling get_session_factory() directly:
    FastAPI tears down request-scoped dependencies (including the `db`
    session from get_db) as part of sending the response, before running
    background tasks, so a background task needs a session of its own
    rather than reusing an already-closed one. Tests, which run an entire
    request inside one shared, SAVEPOINT-wrapped session for isolation,
    override this to yield that same session instead — a disconnected one
    would never see a test's not-yet-(really)-committed data.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> bool:
    """Best-effort connectivity check used by the health endpoint.

    Domain models and migrations arrive in Milestone 2; this only confirms
    the configured database is reachable.
    """
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as error:
        logger.warning("Database connectivity check failed: %s", type(error).__name__)
        return False
