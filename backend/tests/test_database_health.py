from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import get_db
from app.main import app


def test_database_health_returns_connected(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get("/api/v1/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


def test_database_health_returns_503_when_database_fails(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = api_client

    class UnavailableSession:
        def execute(self, statement):
            raise OperationalError(statement, {}, RuntimeError("database unavailable"))

    def unavailable_db() -> Generator[UnavailableSession, None, None]:
        yield UnavailableSession()

    monkeypatch.setitem(app.dependency_overrides, get_db, unavailable_db)

    response = client.get("/api/v1/health/db")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
