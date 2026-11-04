import os
from collections.abc import Generator

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://localhost/siberlens")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.core.auth import get_current_user
from app.services.rss_sync_service import get_rss_sync_lock
from app.db.session import get_db
from app.main import app


@pytest.fixture
def api_client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        with test_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-analyst",
        "email": "analyst@example.test",
    }
    app.dependency_overrides[get_rss_sync_lock] = lambda: True
    try:
        with TestClient(app) as client:
            yield client, test_session
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_rss_sync_lock, None)
        Base.metadata.drop_all(engine)
        engine.dispose()
