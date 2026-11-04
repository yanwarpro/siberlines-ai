from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import Dataset, RssFeed
from app.schemas.rss_feed import (
    RssFeedCreate,
    RssFeedRead,
    RssFeedUpdate,
    RssSyncResult,
)
from app.services.rss_sync_service import get_rss_sync_lock, sync_rss_sources

router = APIRouter(
    prefix="/rss-feeds",
    tags=["rss-feeds"],
    dependencies=[Depends(get_current_user)],
)


def _feed_read(db: Session, feed_id: UUID) -> RssFeedRead:
    row = db.execute(
        select(
            RssFeed,
            Dataset.name.label("dataset_name"),
            Dataset.row_count.label("row_count"),
        )
        .outerjoin(Dataset, Dataset.id == RssFeed.dataset_id)
        .where(RssFeed.id == feed_id)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="RSS source not found")
    feed, dataset_name, row_count = row
    return RssFeedRead(
        id=feed.id,
        name=feed.name,
        url=feed.url,
        enabled=feed.enabled,
        dataset_id=feed.dataset_id,
        dataset_name=dataset_name,
        row_count=row_count or 0,
        last_synced_at=feed.last_synced_at,
        last_sync_status=feed.last_sync_status,
        last_sync_error=feed.last_sync_error,
        created_at=feed.created_at,
        updated_at=feed.updated_at,
    )


@router.get("", response_model=list[RssFeedRead])
def list_rss_feeds(db: Session = Depends(get_db)) -> list[RssFeedRead]:
    try:
        ids = db.scalars(select(RssFeed.id).order_by(RssFeed.created_at, RssFeed.id)).all()
        return [_feed_read(db, feed_id) for feed_id in ids]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while reading RSS sources",
        ) from error


@router.post("", response_model=RssFeedRead, status_code=status.HTTP_201_CREATED)
def create_rss_feed(
    payload: RssFeedCreate,
    db: Session = Depends(get_db),
) -> RssFeedRead:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="RSS source name cannot be blank")
    feed = RssFeed(name=name, url=str(payload.url), enabled=True)
    try:
        with db.begin():
            dataset = Dataset(
                name=name,
                source_type="rss_feed",
                row_count=0,
                status="waiting_for_sync",
            )
            db.add(dataset)
            db.flush()
            feed.dataset_id = dataset.id
            db.add(feed)
            db.flush()
        return _feed_read(db, feed.id)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="An RSS source with this URL already exists",
        ) from error
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while creating the RSS source",
        ) from error


@router.patch("/{feed_id}", response_model=RssFeedRead)
def update_rss_feed(
    feed_id: UUID,
    payload: RssFeedUpdate,
    db: Session = Depends(get_db),
) -> RssFeedRead:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one field to update")
    if any(value is None for value in updates.values()):
        raise HTTPException(status_code=422, detail="Updated RSS source fields cannot be null")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
        if not updates["name"]:
            raise HTTPException(status_code=422, detail="RSS source name cannot be blank")
    if "url" in updates and updates["url"] is not None:
        updates["url"] = str(updates["url"])

    try:
        with db.begin():
            feed = db.get(RssFeed, feed_id)
            if feed is None:
                raise HTTPException(status_code=404, detail="RSS source not found")
            for key, value in updates.items():
                setattr(feed, key, value)
            if "name" in updates and feed.dataset_id:
                dataset = db.get(Dataset, feed.dataset_id)
                if dataset is not None:
                    dataset.name = updates["name"]
            db.flush()
        return _feed_read(db, feed_id)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail="An RSS source with this URL already exists",
        ) from error
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while updating the RSS source",
        ) from error


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rss_feed(feed_id: UUID, db: Session = Depends(get_db)) -> Response:
    try:
        with db.begin():
            feed = db.get(RssFeed, feed_id)
            if feed is None:
                raise HTTPException(status_code=404, detail="RSS source not found")
            db.delete(feed)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while removing the RSS source",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{feed_id}/sync", response_model=RssSyncResult)
def sync_rss_feed(
    feed_id: UUID,
    db: Session = Depends(get_db),
    lock_acquired: bool = Depends(get_rss_sync_lock),
) -> RssSyncResult:
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RSS synchronization is already running",
            headers={"Retry-After": "60"},
        )
    feed = db.get(RssFeed, feed_id)
    if feed is None:
        raise HTTPException(status_code=404, detail="RSS source not found")
    if not feed.enabled:
        raise HTTPException(status_code=409, detail="Enable this RSS source before syncing")

    try:
        run = sync_rss_sources(db, "manual", feed_id)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while recording RSS synchronization",
        ) from error

    if run.status == "failed":
        raise HTTPException(
            status_code=502,
            detail=run.error_summary or "RSS synchronization failed",
        )
    feed = db.get(RssFeed, feed_id)
    if feed is None or feed.dataset_id is None:
        raise HTTPException(status_code=503, detail="RSS dataset is unavailable after synchronization")
    return RssSyncResult(
        feed_id=feed.id,
        dataset_id=feed.dataset_id,
        items_received=run.items_received,
        items_inserted=run.new_articles,
        duplicates_skipped=run.duplicate_articles,
        invalid_items=run.invalid_articles,
        synced_at=run.completed_at or datetime.now(timezone.utc),
    )
