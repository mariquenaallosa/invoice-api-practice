from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = settings.test_database_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]

engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)


def upgrade_test_database() -> None:
    """Apply the Alembic migrations to the test database.

    Alembic is the only source of truth for the schema: the test database is
    migrated exactly like the application database instead of being built from
    the SQLAlchemy metadata.
    """
    config = Config()
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def prepare_database() -> Generator[None, None, None]:
    upgrade_test_database()
    yield
    engine.dispose()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Session bound to a connection wrapped in an outer transaction.

    Every statement runs inside that outer transaction, so whatever the test
    commits is rolled back when the test ends and tests stay isolated.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client_raising(db_session: Session) -> Generator[TestClient, None, None]:
    """Test client that turns unhandled exceptions into HTTP responses."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
