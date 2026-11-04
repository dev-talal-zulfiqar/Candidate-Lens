import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from alembic import command

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
    """A database session scoped to a transaction that is always rolled back.

    Keeps each test isolated without needing to recreate the schema.
    """
    engine = create_engine(TEST_DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session: Session = session_factory()

    try:
        yield session
    finally:
        session.close()
        # A failed flush (e.g. a constraint violation under test) already
        # leaves the DBAPI connection's transaction rolled back; rolling
        # back again here would just emit a harmless SAWarning.
        if transaction.is_active:
            transaction.rollback()
        connection.close()
        engine.dispose()
