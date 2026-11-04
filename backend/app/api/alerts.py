from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import Alert, Analysis, Dataset
from app.models.alert import ALERT_STATUSES
from app.schemas.alert import (
    AlertDetail,
    AlertListItem,
    AlertListPage,
    AlertNote,
    AlertNoteCreate,
    AlertStatusUpdate,
    AlertSummary,
)
from app.services.alert_service import add_analyst_note, apply_status_change

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
    dependencies=[Depends(get_current_user)],
)

RESOLVED_STATUSES = ("resolved", "dismissed")
HIGH_PRIORITY_SEVERITIES = ("high", "critical")

def _list_columns() -> tuple[Any, ...]:
    return (
        Alert.id,
        Alert.analysis_id,
        Alert.dataset_id,
        Alert.narrative_key,
        Alert.narrative_cluster_id,
        Alert.episode_id,
        Alert.severity,
        Alert.baseline_count,
        Alert.observed_count,
        Alert.evidence_json,
        Alert.explanation,
        Alert.status,
        Alert.detection_interval_start,
        Alert.detection_interval_end,
        Alert.detected_at,
        Alert.fingerprint,
        Alert.status_history_json,
        Alert.analyst_notes_json,
        Alert.created_at,
        Alert.updated_at,
        Dataset.name.label("dataset_name"),
        Analysis.created_at.label("analysis_created_at"),
    )

def _base_query():
    return (
        select(*_list_columns())
        .join(Analysis, Analysis.id == Alert.analysis_id)
        .outerjoin(Dataset, Dataset.id == Alert.dataset_id)
    )

def _alert_detail(db: Session, alert_id: UUID) -> AlertDetail:
    row = db.execute(
        _base_query().where(Alert.id == alert_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertDetail(**row)

@router.get("", response_model=AlertListPage)
def list_alerts(
    severity: str | None = Query(default=None, max_length=20),
    status: str | None = Query(default=None, max_length=20),
    dataset_id: UUID | None = Query(default=None),
    detected_from: datetime | None = Query(default=None),
    detected_to: datetime | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AlertListPage:
    if status is not None and status not in ALERT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown status '{status}'. Allowed values: "
                f"{', '.join(ALERT_STATUSES)}"
            ),
        )
    if detected_from and detected_to and detected_from > detected_to:
        raise HTTPException(
            status_code=422,
            detail="detected_from must be earlier than or equal to detected_to",
        )

    filters = []
    if severity is not None:
        filters.append(func.lower(Alert.severity) == severity.strip().lower())
    if status is not None:
        filters.append(Alert.status == status)
    if dataset_id is not None:
        filters.append(Alert.dataset_id == dataset_id)
    if detected_from is not None:
        filters.append(Alert.detected_at >= detected_from)
    if detected_to is not None:
        filters.append(Alert.detected_at <= detected_to)

    query = _base_query()
    count_query = select(func.count(Alert.id))
    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)

    try:
        total = db.scalar(count_query) or 0
        rows = db.execute(
            query.order_by(
                Alert.detected_at.desc().nullslast(),
                Alert.created_at.desc(),
                Alert.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).mappings()
        items = [AlertListItem(**row) for row in rows]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while reading alerts",
        ) from error

    return AlertListPage(items=items, total=total, limit=limit, offset=offset)

@router.get("/summary", response_model=AlertSummary)
def get_alert_summary(db: Session = Depends(get_db)) -> AlertSummary:
    try:
        status_rows = db.execute(
            select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
        ).all()
        severity_rows = db.execute(
            select(func.lower(Alert.severity), func.count(Alert.id)).group_by(
                func.lower(Alert.severity)
            )
        ).all()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while summarising alerts",
        ) from error

    status_counts = {status: count for status, count in status_rows}
    severity_counts = {severity: count for severity, count in severity_rows}
    total = sum(status_counts.values())
    resolved = status_counts.get("resolved", 0)
    dismissed = status_counts.get("dismissed", 0)
    return AlertSummary(
        total=total,
        new=status_counts.get("new", 0),
        pending_review=status_counts.get("pending_review", 0),
        under_review=status_counts.get("under_review", 0),
        resolved=resolved,
        dismissed=dismissed,
        high_priority=sum(
            severity_counts.get(severity, 0) for severity in HIGH_PRIORITY_SEVERITIES
        ),
        medium_priority=severity_counts.get("medium", 0),
        open_total=total - resolved - dismissed,
    )

@router.get("/{alert_id}", response_model=AlertDetail)
def get_alert(alert_id: UUID, db: Session = Depends(get_db)) -> AlertDetail:
    try:
        return _alert_detail(db, alert_id)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while reading the alert",
        ) from error

@router.patch("/{alert_id}/status", response_model=AlertDetail)
def update_alert_status(
    alert_id: UUID,
    payload: AlertStatusUpdate,
    db: Session = Depends(get_db),
) -> AlertDetail:
    note = payload.note.strip() if payload.note else None
    try:
        with db.begin():
            alert = db.get(Alert, alert_id)
            if alert is None:
                raise HTTPException(status_code=404, detail="Alert not found")
            apply_status_change(alert, payload.status, note or None)
            db.flush()
        return _alert_detail(db, alert_id)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while updating the alert status",
        ) from error

@router.post("/{alert_id}/notes", response_model=AlertNote, status_code=201)
def create_alert_note(
    alert_id: UUID,
    payload: AlertNoteCreate,
    db: Session = Depends(get_db),
) -> AlertNote:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Note body cannot be blank")
    try:
        with db.begin():
            alert = db.get(Alert, alert_id)
            if alert is None:
                raise HTTPException(status_code=404, detail="Alert not found")
            note = add_analyst_note(alert, body)
            db.flush()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while saving the alert note",
        ) from error

    return AlertNote(**note)
