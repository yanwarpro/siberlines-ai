import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated, Iterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models import RssSyncRun
from app.schemas.rss_feed import RssSyncRunRead, RssSyncStatus
from app.services.rss_sync_service import (
    get_rss_sync_lock,
    sync_rss_sources,
)

router = APIRouter(prefix="/rss-sync", tags=["rss-sync"])


def _require_scheduled_secret(
    provided_secret: Annotated[str | None, Header(alias="X-RSS-Sync-Secret")] = None,
) -> None:
    configured_secret = get_settings().rss_sync_secret
    if configured_secret is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduled RSS synchronization is not configured",
        )
    if provided_secret is None or not hmac.compare_digest(
        configured_secret.get_secret_value(),
        provided_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid scheduled synchronization secret",
        )


def _get_scheduled_sync_lock(
    _authorized: None = Depends(_require_scheduled_secret),
    acquired: bool = Depends(get_rss_sync_lock),
) -> Iterator[bool]:
    yield acquired


@router.post("/scheduled", response_model=RssSyncRunRead)
def run_scheduled_rss_sync(
    db: Session = Depends(get_db),
    lock_acquired: bool = Depends(_get_scheduled_sync_lock),
) -> RssSyncRunRead:
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="RSS synchronization is already running",
            headers={"Retry-After": "60"},
        )
    return sync_rss_sources(db, "scheduled")


@router.get(
    "/status",
    response_model=RssSyncStatus,
    dependencies=[Depends(get_current_user)],
)
def get_rss_sync_status(db: Session = Depends(get_db)) -> RssSyncStatus:
    settings = get_settings()
    try:
        latest = db.scalar(
            select(RssSyncRun)
            .order_by(RssSyncRun.started_at.desc(), RssSyncRun.id.desc())
            .limit(1)
        )
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not read RSS synchronization status",
        ) from error

    next_scheduled_at = None
    if settings.rss_sync_schedule_enabled:
        now = datetime.now(timezone.utc)
        next_scheduled_at = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return RssSyncStatus(
        schedule_enabled=settings.rss_sync_schedule_enabled,
        schedule_interval_minutes=60,
        next_scheduled_at=next_scheduled_at,
        latest_run=latest,
    )


@router.get(
    "/history",
    response_model=list[RssSyncRunRead],
    dependencies=[Depends(get_current_user)],
)
def get_rss_sync_history(
    db: Session = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50),
) -> list[RssSyncRunRead]:
    try:
        return list(
            db.scalars(
                select(RssSyncRun)
                .order_by(RssSyncRun.started_at.desc(), RssSyncRun.id.desc())
                .limit(limit)
            ).all()
        )
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not read RSS synchronization history",
        ) from error
