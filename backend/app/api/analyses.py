from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models import Alert, Analysis, Dataset, Post
from app.schemas.analysis import AnalysisDetail, AnalystNote, AnalystNoteCreate
from app.schemas.alert import AlertRead
from app.services.alert_service import record_alert
from app.services.analysis_service import (
    DEFAULT_TEMPORAL_GAP_HOURS,
    analyze_posts,
)

router = APIRouter(tags=["analyses"], dependencies=[Depends(get_current_user)])


def _analysis_detail(db: Session, analysis: Analysis) -> AnalysisDetail:
    alerts = db.scalars(
        select(Alert)
        .where(Alert.analysis_id == analysis.id)
        .order_by(Alert.created_at, Alert.id)
    ).all()
    return AnalysisDetail(
        id=analysis.id,
        dataset_id=analysis.dataset_id,
        status=analysis.status,
        config_json=analysis.config_json,
        metrics_json=analysis.metrics_json,
        notes_json=analysis.notes_json or [],
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
        alerts=alerts,
    )


@router.post(
    "/datasets/{dataset_id}/analyses",
    response_model=AnalysisDetail,
    status_code=201,
)
def create_dataset_analysis(
    dataset_id: UUID,
    temporal_gap_hours: float = Query(
        default=DEFAULT_TEMPORAL_GAP_HOURS,
        gt=0,
        le=168,
    ),
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    try:
        with db.begin():
            dataset = db.get(Dataset, dataset_id)
            if dataset is None:
                raise HTTPException(status_code=404, detail="Dataset not found")

            posts = db.scalars(
                select(Post)
                .where(Post.dataset_id == dataset_id)
                .order_by(Post.timestamp, Post.id)
            ).all()
            if not posts:
                raise HTTPException(
                    status_code=422,
                    detail="Cannot analyze a dataset with no posts",
                )

            metrics, alert_data = analyze_posts(posts, temporal_gap_hours)
            analysis = Analysis(
                dataset_id=dataset_id,
                status="completed",
                config_json={
                    "method": "tfidf_cosine_and_hourly_baseline",
                    "similarity_threshold": metrics["summary"]["similarity_threshold"],
                    "temporal_gap_hours": temporal_gap_hours,
                },
                metrics_json=metrics,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(analysis)
            db.flush()
            if alert_data is not None:
                record_alert(db, analysis.id, dataset_id, alert_data)
            db.flush()
            db.refresh(analysis)
            detail = _analysis_detail(db, analysis)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while running analysis",
        ) from error

    return detail


@router.get(
    "/datasets/{dataset_id}/analyses",
    response_model=list[AnalysisDetail],
)
def list_dataset_analyses(
    dataset_id: UUID,
    db: Session = Depends(get_db),
) -> list[AnalysisDetail]:
    try:
        if db.get(Dataset, dataset_id) is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        analyses = db.scalars(
            select(Analysis)
            .where(Analysis.dataset_id == dataset_id)
            .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .limit(50)
        ).all()
        return [_analysis_detail(db, analysis) for analysis in analyses]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while reading analyses",
        ) from error


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: UUID,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    try:
        analysis = db.get(Analysis, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return _analysis_detail(db, analysis)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while reading analysis",
        ) from error

@router.get("/analyses/{analysis_id}/alerts", response_model=list[AlertRead])
def list_analysis_alerts(
    analysis_id: UUID,
    db: Session = Depends(get_db),
) -> list[AlertRead]:
    try:
        if db.get(Analysis, analysis_id) is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        alerts = db.scalars(
            select(Alert)
            .where(Alert.analysis_id == analysis_id)
            .order_by(Alert.created_at, Alert.id)
        ).all()
        return [AlertRead.model_validate(alert) for alert in alerts]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while reading analysis alerts",
        ) from error

@router.post(
    "/analyses/{analysis_id}/notes",
    response_model=AnalystNote,
    status_code=201,
)
def create_analyst_note(
    analysis_id: UUID,
    payload: AnalystNoteCreate,
    db: Session = Depends(get_db),
) -> AnalystNote:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Note body cannot be blank")
    try:
        with db.begin():
            analysis = db.get(Analysis, analysis_id)
            if analysis is None:
                raise HTTPException(status_code=404, detail="Analysis not found")
            note = {
                "note_id": str(uuid4()),
                "episode_id": payload.episode_id,
                "narrative_cluster_id": payload.narrative_cluster_id,
                "body": body,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            analysis.notes_json = [*(analysis.notes_json or []), note]
            db.flush()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while saving the note",
        ) from error

    return AnalystNote(**note)

@router.delete(
    "/analyses/{analysis_id}/notes/{note_id}",
    response_model=AnalysisDetail,
)
def delete_analyst_note(
    analysis_id: UUID,
    note_id: UUID,
    db: Session = Depends(get_db),
) -> AnalysisDetail:
    try:
        with db.begin():
            analysis = db.get(Analysis, analysis_id)
            if analysis is None:
                raise HTTPException(status_code=404, detail="Analysis not found")
            existing = analysis.notes_json or []
            remaining = [
                note for note in existing if note.get("note_id") != str(note_id)
            ]
            if len(remaining) == len(existing):
                raise HTTPException(status_code=404, detail="Note not found")
            analysis.notes_json = remaining
            db.flush()
            detail = _analysis_detail(db, analysis)
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable while deleting the note",
        ) from error

    return detail
