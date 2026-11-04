from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Literal
from uuid import UUID

from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models import RssFeed, RssSyncRun
from app.services.rss_service import RssFeedError, fetch_rss_feed, persist_rss_items

logger = logging.getLogger(__name__)

RSS_SYNC_LOCK_KEY = 0x53494245524C454E
_LOCAL_SYNC_LOCK = threading.Lock()
SyncTrigger = Literal["manual", "scheduled"]


@contextmanager
def rss_sync_lock(bind: Engine | None = None) -> Iterator[bool]:
    target = bind or engine
    if target.dialect.name != "postgresql":
        acquired = _LOCAL_SYNC_LOCK.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                _LOCAL_SYNC_LOCK.release()
        return

    with target.connect() as connection:
        transaction = connection.begin()
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
                {"lock_key": RSS_SYNC_LOCK_KEY},
            ).scalar_one()
        )
        try:
            yield acquired
        finally:
            transaction.rollback()


def get_rss_sync_lock() -> Iterator[bool]:
    with rss_sync_lock() as acquired:
        yield acquired


def _failure_status(feed: RssFeed, detail: str) -> None:
    feed.last_synced_at = datetime.now(timezone.utc)
    feed.last_sync_status = "failed"
    feed.last_sync_error = detail[:2000]


def sync_rss_sources(
    session: Session,
    trigger_type: SyncTrigger,
    feed_id: UUID | None = None,
) -> RssSyncRun:
    if feed_id is None:
        feeds = session.scalars(
            select(RssFeed)
            .where(RssFeed.enabled.is_(True))
            .order_by(RssFeed.created_at, RssFeed.id)
        ).all()
    else:
        feed = session.get(RssFeed, feed_id)
        if feed is None:
            raise LookupError("RSS source not found")
        feeds = [feed]

    started_at = datetime.now(timezone.utc)
    stale_runs = session.scalars(
        select(RssSyncRun).where(RssSyncRun.status == "running")
    ).all()
    for stale_run in stale_runs:
        stale_run.status = "failed"
        stale_run.completed_at = started_at
        stale_run.error_summary = "The previous synchronization ended before reporting completion."

    run = RssSyncRun(
        trigger_type=trigger_type,
        status="running",
        source_feed_id=feed_id,
        source_name=feeds[0].name if feed_id is not None and feeds else None,
        started_at=started_at,
        total_sources=len(feeds),
    )
    session.add(run)
    session.commit()
    run_id = run.id

    successful_sources = 0
    failed_sources = 0
    items_received = 0
    new_articles = 0
    duplicate_articles = 0
    invalid_articles = 0
    errors: list[str] = []

    for candidate in feeds:
        current_feed = session.get(RssFeed, candidate.id)
        if current_feed is None:
            failed_sources += 1
            errors.append(f"{candidate.name}: source was removed during synchronization")
            continue
        try:
            parsed_feed = fetch_rss_feed(current_feed)
        except RssFeedError as error:
            _failure_status(current_feed, str(error))
            session.commit()
            failed_sources += 1
            errors.append(f"{current_feed.name}: {error}")
            continue
        except Exception as error:
            logger.exception("Unexpected RSS fetch failure for source %s", candidate.id)
            detail = f"Unexpected feed fetch failure ({type(error).__name__})"
            _failure_status(current_feed, detail)
            session.commit()
            failed_sources += 1
            errors.append(f"{current_feed.name}: {detail}")
            continue

        try:
            result = persist_rss_items(session, current_feed, parsed_feed)
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Could not persist RSS items for source %s", candidate.id)
            failed_sources += 1
            errors.append(f"{candidate.name}: items could not be saved to the database")
            try:
                failed_feed = session.get(RssFeed, candidate.id)
                if failed_feed is not None:
                    _failure_status(failed_feed, errors[-1])
                    session.commit()
            except SQLAlchemyError:
                session.rollback()
                logger.exception("Could not save RSS failure status for source %s", candidate.id)
            continue

        successful_sources += 1
        items_received += result.items_received
        new_articles += result.items_inserted
        duplicate_articles += result.duplicates_skipped
        invalid_articles += result.invalid_items

    if failed_sources == 0:
        status = "successful"
    elif successful_sources:
        status = "partial_success"
    else:
        status = "failed"

    completed_at = datetime.now(timezone.utc)
    completed_run = session.get(RssSyncRun, run_id)
    if completed_run is None:
        raise RuntimeError("RSS synchronization history row disappeared")
    completed_run.status = status
    completed_run.completed_at = completed_at
    completed_run.successful_sources = successful_sources
    completed_run.failed_sources = failed_sources
    completed_run.items_received = items_received
    completed_run.new_articles = new_articles
    completed_run.duplicate_articles = duplicate_articles
    completed_run.invalid_articles = invalid_articles
    completed_run.error_summary = "\n".join(errors)[:8000] or None
    session.commit()
    return completed_run
