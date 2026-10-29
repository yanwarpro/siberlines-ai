from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Alert, Analysis, Dataset, Post
from app.schemas.analysis import AnalysisDetail
from app.services.analysis_service import analyze_posts

router = APIRouter(tags=["analyses"])


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

            metrics, alert_data = analyze_posts(posts)
            analysis = Analysis(
                dataset_id=dataset_id,
                status="completed",
                config_json={
                    "method": "tfidf_cosine_and_hourly_baseline",
                    "similarity_threshold": metrics["summary"]["similarity_threshold"],
                },
                metrics_json=metrics,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(analysis)
            db.flush()
            if alert_data is not None:
                db.add(Alert(analysis_id=analysis.id, status="new", **alert_data))
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
