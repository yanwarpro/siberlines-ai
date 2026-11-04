from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.auth import get_current_user
from app.main import app
from app.models import Dataset, Post, RssFeed, RssSyncRun
from app.services.rss_service import ParsedRssFeed, RssFeedError, RssItem
from app.services.rss_sync_service import get_rss_sync_lock, rss_sync_lock

SYNC_SECRET = "test-rss-sync-secret-that-is-long-enough"


def _settings(schedule_enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        rss_sync_secret=SecretStr(SYNC_SECRET),
        rss_sync_schedule_enabled=schedule_enabled,
    )


def _parsed_feed(urls: tuple[str, ...]) -> ParsedRssFeed:
    return ParsedRssFeed(
        items=[
            RssItem(
                title=f"Security advisory {index}",
                description="Verified test feed item",
                url=url,
                published_at=datetime(2026, 11, 4, 12, index, tzinfo=timezone.utc),
            )
            for index, url in enumerate(urls, start=1)
        ],
        invalid_items=0,
    )


def _create_feed(client: TestClient, name: str, url: str) -> dict[str, object]:
    response = client.post("/api/v1/rss-feeds", json={"name": name, "url": url})
    assert response.status_code == 201
    return response.json()


def test_scheduled_sync_imports_and_repeat_sync_skips_canonical_duplicates(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch,
) -> None:
    client, test_session = api_client
    source = _create_feed(client, "Canonical test", "https://feed.example.test/rss.xml")
    monkeypatch.setattr("app.api.rss_sync.get_settings", _settings)
    monkeypatch.setattr(
        "app.services.rss_sync_service.fetch_rss_feed",
        lambda _feed: _parsed_feed(("https://Example.test:443/advisory/1",)),
    )

    first = client.post(
        "/api/v1/rss-sync/scheduled",
        headers={"X-RSS-Sync-Secret": SYNC_SECRET},
    )
    second = client.post(
        "/api/v1/rss-sync/scheduled",
        headers={"X-RSS-Sync-Secret": SYNC_SECRET},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "successful"
    assert first.json()["new_articles"] == 1
    assert second.status_code == 200
    assert second.json()["new_articles"] == 0
    assert second.json()["duplicate_articles"] == 1
    with test_session() as session:
        dataset = session.get(Dataset, UUID(str(source["dataset_id"])))
        assert dataset is not None
        assert dataset.row_count == 1
        assert len(session.scalars(select(Post).where(Post.dataset_id == dataset.id)).all()) == 1
        runs = session.scalars(
            select(RssSyncRun).order_by(RssSyncRun.started_at)
        ).all()
        assert [run.status for run in runs] == ["successful", "successful"]
        assert [run.trigger_type for run in runs] == ["scheduled", "scheduled"]


def test_failed_source_does_not_prevent_other_sources_from_syncing(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch,
) -> None:
    client, test_session = api_client
    failed = _create_feed(client, "Unavailable feed", "https://failed.example.test/rss.xml")
    successful = _create_feed(client, "Healthy feed", "https://healthy.example.test/rss.xml")
    monkeypatch.setattr("app.api.rss_sync.get_settings", _settings)

    def fetch(feed: RssFeed) -> ParsedRssFeed:
        if feed.id == UUID(str(failed["id"])):
            raise RssFeedError("upstream unavailable")
        return _parsed_feed(("https://healthy.example.test/advisory/1",))

    monkeypatch.setattr("app.services.rss_sync_service.fetch_rss_feed", fetch)
    response = client.post(
        "/api/v1/rss-sync/scheduled",
        headers={"X-RSS-Sync-Secret": SYNC_SECRET},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "partial_success"
    assert response.json()["successful_sources"] == 1
    assert response.json()["failed_sources"] == 1
    assert "Unavailable feed: upstream unavailable" in response.json()["error_summary"]
    with test_session() as session:
        stored_feed = session.get(RssFeed, UUID(str(failed["id"])))
        assert stored_feed is not None
        assert stored_feed.last_sync_status == "failed"
        assert session.scalar(
            select(Dataset.row_count).where(Dataset.id == UUID(str(successful["dataset_id"])))
        ) == 1


def test_scheduled_sync_rejects_invalid_secret_without_running(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch,
) -> None:
    client, test_session = api_client
    _create_feed(client, "Must not run", "https://secure.example.test/rss.xml")
    monkeypatch.setattr("app.api.rss_sync.get_settings", _settings)
    monkeypatch.setattr(
        "app.services.rss_sync_service.fetch_rss_feed",
        lambda _feed: _parsed_feed(("https://secure.example.test/advisory/1",)),
    )

    response = client.post(
        "/api/v1/rss-sync/scheduled",
        headers={"X-RSS-Sync-Secret": "wrong-secret"},
    )

    assert response.status_code == 401
    with test_session() as session:
        assert session.scalar(select(RssSyncRun)) is None


def test_overlapping_sync_is_rejected_for_manual_and_scheduled_requests(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch,
) -> None:
    client, test_session = api_client
    source = _create_feed(client, "Locked feed", "https://locked.example.test/rss.xml")
    monkeypatch.setattr("app.api.rss_sync.get_settings", _settings)
    original_override = app.dependency_overrides[get_rss_sync_lock]
    app.dependency_overrides[get_rss_sync_lock] = lambda: False
    try:
        scheduled = client.post(
            "/api/v1/rss-sync/scheduled",
            headers={"X-RSS-Sync-Secret": SYNC_SECRET},
        )
        manual = client.post(f"/api/v1/rss-feeds/{source['id']}/sync")
    finally:
        app.dependency_overrides[get_rss_sync_lock] = original_override

    assert scheduled.status_code == 409
    assert manual.status_code == 409
    with test_session() as session:
        assert session.scalar(select(RssSyncRun)) is None


def test_sync_status_and_history_are_persisted_and_return_schedule_estimate(
    api_client: tuple[TestClient, sessionmaker[Session]],
    monkeypatch,
) -> None:
    client, test_session = api_client
    source = _create_feed(client, "History feed", "https://history.example.test/rss.xml")
    monkeypatch.setattr("app.api.rss_sync.get_settings", _settings)
    monkeypatch.setattr(
        "app.services.rss_sync_service.fetch_rss_feed",
        lambda _feed: _parsed_feed(("https://history.example.test/advisory/1",)),
    )
    manual = client.post(f"/api/v1/rss-feeds/{source['id']}/sync")
    assert manual.status_code == 200

    status_response = client.get("/api/v1/rss-sync/status")
    history_response = client.get("/api/v1/rss-sync/history?limit=5")

    assert status_response.status_code == 200
    assert status_response.json()["schedule_enabled"] is True
    assert status_response.json()["schedule_interval_minutes"] == 60
    assert status_response.json()["next_scheduled_at"] is not None
    assert status_response.json()["latest_run"]["status"] == "successful"
    assert history_response.status_code == 200
    assert len(history_response.json()) == 1
    assert history_response.json()[0]["trigger_type"] == "manual"
    assert history_response.json()[0]["source_name"] == "History feed"
    with test_session() as session:
        assert session.scalar(select(RssSyncRun)).completed_at is not None


def test_sqlite_sync_lock_rejects_nested_overlapping_work(api_client) -> None:
    _, test_session = api_client
    bind = test_session.kw["bind"]
    with rss_sync_lock(bind):
        with rss_sync_lock(bind) as overlapping:
            assert overlapping is False


def test_sync_status_requires_supabase_auth(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client
    auth_override = app.dependency_overrides.pop(get_current_user)
    try:
        response = client.get("/api/v1/rss-sync/status")
    finally:
        app.dependency_overrides[get_current_user] = auth_override
    assert response.status_code == 401
