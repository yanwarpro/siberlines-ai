from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import get_current_user
from app.main import app
from app.models import Analysis, Dataset, Post, RssFeed
from app.services.rss_service import ParsedRssFeed, RssItem


def test_rss_feed_lifecycle_keeps_dataset_when_source_is_removed(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    response = client.post(
        "/api/v1/rss-feeds",
        json={"name": "Test Security Feed", "url": "https://example.test/rss.xml"},
    )
    assert response.status_code == 201
    source = response.json()
    assert source["dataset_name"] == "Test Security Feed"
    dataset_id = source["dataset_id"]

    updated = client.patch(
        f"/api/v1/rss-feeds/{source['id']}",
        json={"enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    deleted = client.delete(f"/api/v1/rss-feeds/{source['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/v1/rss-feeds").json() == []

    with test_session() as session:
        dataset = session.get(Dataset, UUID(dataset_id))
        assert dataset is not None
        assert dataset.source_type == "rss_feed"
        assert session.scalar(select(RssFeed)) is None


def test_rss_sync_stores_posts_and_dataset_can_be_analyzed(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch,
) -> None:
    client, test_session = api_client
    source = client.post(
        "/api/v1/rss-feeds",
        json={"name": "Test Security Feed", "url": "https://example.test/rss.xml"},
    ).json()
    parsed = ParsedRssFeed(
        items=[
            RssItem(
                title="Security update for critical infrastructure",
                description=f"Advisory details about vulnerability {index}",
                url=f"https://example.test/advisory/{index}",
                published_at=datetime(2026, 11, 3, 12, index, tzinfo=timezone.utc),
            )
            for index in (1, 2)
        ],
        invalid_items=0,
    )
    monkeypatch.setattr("app.services.rss_sync_service.fetch_rss_feed", lambda _feed: parsed)

    synced = client.post(f"/api/v1/rss-feeds/{source['id']}/sync")
    assert synced.status_code == 200
    assert synced.json()["items_inserted"] == 2
    assert synced.json()["dataset_id"] == source["dataset_id"]

    with test_session() as session:
        posts = session.scalars(select(Post).order_by(Post.timestamp)).all()
        assert len(posts) == 2
        assert posts[0].source_url == "https://example.test/advisory/1"
        assert posts[0].source_id.startswith("rss:")
        assert session.get(Dataset, UUID(source["dataset_id"])).row_count == 2

    analysis = client.post(f"/api/v1/datasets/{source['dataset_id']}/analyses")
    assert analysis.status_code == 201
    with test_session() as session:
        assert session.scalar(select(Analysis)) is not None


def test_rss_management_requires_a_supabase_session(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    override = app.dependency_overrides.pop(get_current_user)
    try:
        response = client.get("/api/v1/rss-feeds")
    finally:
        app.dependency_overrides[get_current_user] = override
    assert response.status_code == 401


def test_rss_feed_rejects_non_https_and_duplicate_sources(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    insecure = client.post(
        "/api/v1/rss-feeds",
        json={"name": "Unsafe feed", "url": "http://example.test/rss.xml"},
    )
    assert insecure.status_code == 422

    payload = {"name": "Safe feed", "url": "https://example.test/rss.xml"}
    created = client.post("/api/v1/rss-feeds", json=payload)
    duplicate = client.post("/api/v1/rss-feeds", json={**payload, "name": "Duplicate"})
    assert created.status_code == 201
    assert duplicate.status_code == 409
