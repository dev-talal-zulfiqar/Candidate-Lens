import contextlib
import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.services import jobs as jobs_service
from app.services import resume_upload

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://candidatelens:candidatelens@localhost:5432/candidatelens_test",
)

if "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1]:
    raise RuntimeError(
        "TEST_DATABASE_URL does not look like a test database "
        f"({TEST_DATABASE_URL!r}) — refusing to run migrations against it."
    )


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    """Apply Alembic migrations to the isolated test database once per run."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")
    yield


@pytest.fixture()
def db_session():
    """A database session whose changes are always rolled back after the test.

    Route handlers call `session.commit()` in normal operation, which would
    normally end the outer transaction. To keep tests isolated anyway, the
    session actually runs inside a SAVEPOINT that is transparently restarted
    after every commit — the standard SQLAlchemy pattern for testing code
    that commits.
    """
    engine = create_engine(TEST_DATABASE_URL)
    connection = engine.connect()
    outer_transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session: Session = session_factory()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(_session: Session, _transaction: object) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    """App settings pointed at a throwaway per-test storage directory.

    Keeps resume upload tests from ever writing into the real backend/storage
    directory used by manual runs.
    """
    return Settings(resume_storage_dir=str(tmp_path / "resumes"))


@pytest.fixture()
def client(
    db_session: Session, test_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> TestClient:
    """An HTTP test client whose requests share the isolated db_session and
    a throwaway storage directory."""

    def _override_get_db():
        yield db_session

    @contextlib.contextmanager
    def _reuse_db_session_for_background_work():
        # Background tasks (e.g. resume upload processing) normally open a
        # fresh session against the real engine — but that would never see
        # this test's data, since db_session's writes only ever live inside
        # a SAVEPOINT on one shared connection, not a real commit any other
        # connection could observe. Route background work through the same
        # session the rest of the request uses instead, and — unlike the
        # production implementation — don't close it, since the test (and
        # any later requests within it) still owns its lifecycle.
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    monkeypatch.setattr(
        resume_upload, "open_background_session", _reuse_db_session_for_background_work
    )
    monkeypatch.setattr(
        jobs_service, "open_background_session", _reuse_db_session_for_background_work
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_settings, None)
