from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Dataset, Post, RssFeed
from app.services.analysis_service import _evidence
from app.services.rss_service import (
    ParsedRssFeed,
    RssFeedError,
    RssItem,
    fetch_rss_feed,
    parse_rss_feed,
    persist_rss_items,
)


def test_parse_rss_feed_extracts_headline_excerpt_and_utc_timestamp() -> None:
    parsed = parse_rss_feed(
        b"""<?xml version="1.0"?>
        <rss version="2.0"><channel><item>
          <title><![CDATA[Security update]]></title>
          <link>https://example.test/advisory/1</link>
          <description>&lt;p&gt;Short &amp;amp; useful details&lt;/p&gt;</description>
          <pubDate>Tue, 03 Nov 2026 12:00:00 +0000</pubDate>
        </item></channel></rss>"""
    )

    assert parsed.invalid_items == 0
    assert parsed.items == [
        RssItem(
            title="Security update",
            description="Short & useful details",
            url="https://example.test/advisory/1",
            published_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
        )
    ]


def test_parse_rss_feed_rejects_non_https_and_missing_publication_date() -> None:
    parsed = parse_rss_feed(
        b"""<rss><channel>
        <item><title>Unsafe link</title><link>http://example.test/1</link>
          <pubDate>Tue, 03 Nov 2026 12:00:00 +0000</pubDate></item>
        <item><title>Missing date</title><link>https://example.test/2</link></item>
        </channel></rss>"""
    )

    assert parsed.items == []
    assert parsed.invalid_items == 2


def test_parse_rss_feed_rejects_dtd_entity_declarations() -> None:
    with pytest.raises(RssFeedError, match="entity declarations"):
        parse_rss_feed(
            b"""<!DOCTYPE rss [<!ENTITY expansion "blocked">]>
            <rss><channel><item><title>&expansion;</title></item></channel></rss>"""
        )


def test_rss_fetch_rejects_private_dns_results(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.rss_service.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )
    feed = SimpleNamespace(url="https://internal.example.test/feed.xml")
    with pytest.raises(RssFeedError, match="public IP"):
        fetch_rss_feed(feed)


def test_rss_sync_is_idempotent_and_preserves_original_links(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, test_session = api_client
    parsed = ParsedRssFeed(
        items=[
            RssItem(
                title="Security update",
                description="Short excerpt",
                url="https://example.test/advisory/1",
                published_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
            )
        ],
        invalid_items=0,
    )

    with test_session() as session:
        dataset = Dataset(
            name="Test CERT Advisories",
            source_type="rss_feed",
            status="waiting_for_sync",
        )
        session.add(dataset)
        session.flush()
        feed = RssFeed(
            name=dataset.name,
            url="https://feeds.example.test/advisories.xml",
            dataset_id=dataset.id,
        )
        session.add(feed)
        session.commit()
        first = persist_rss_items(session, feed, parsed)
        second = persist_rss_items(session, feed, parsed)

    assert first.items_inserted == 1
    assert second.items_inserted == 0
    assert second.duplicates_skipped == 1

    with test_session() as session:
        dataset = session.scalar(select(Dataset))
        post = session.scalar(select(Post))
        assert dataset is not None
        assert dataset.source_type == "rss_feed"
        assert dataset.row_count == 1
        assert post is not None
        assert post.source_url == "https://example.test/advisory/1"
        assert _evidence(post)["source_url"] == post.source_url


def test_rss_sync_persists_items_in_its_existing_dataset(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    _, test_session = api_client
    parsed = ParsedRssFeed(
        items=[
            RssItem(
                title="Security update",
                description="",
                url="https://example.test/advisory/1",
                published_at=datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc),
            )
        ],
        invalid_items=0,
    )

    with test_session() as session:
        dataset = Dataset(
            name="Test CERT Advisories",
            source_type="rss_feed",
            status="waiting_for_sync",
        )
        session.add(dataset)
        session.flush()
        feed = RssFeed(
            name=dataset.name,
            url="https://feeds.example.test/advisories.xml",
            dataset_id=dataset.id,
        )
        session.add(feed)
        session.commit()
        result = persist_rss_items(session, feed, parsed)
        assert result.items_inserted == 1
