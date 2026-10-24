from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app

UNREACHABLE_DATABASE_URL = "postgresql+psycopg://invoice:invoice@127.0.0.1:1/invoice_test"


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_returns_503_when_database_is_unreachable(client: TestClient) -> None:
    unreachable_engine = create_engine(UNREACHABLE_DATABASE_URL, future=True)

    def override_get_db() -> Generator[Session, None, None]:
        session = Session(bind=unreachable_engine)
        try:
            yield session
        finally:
            session.close()
            unreachable_engine.dispose()

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
