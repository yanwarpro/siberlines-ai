from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Dataset, Post
from app.schemas.dataset import DatasetSummary

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _dataset_summary_statement():
    return (
        select(
            Dataset.id,
            Dataset.name,
            Dataset.source,
            Dataset.status,
            Dataset.created_at,
            Dataset.updated_at,
            func.count(Post.id).label("post_count"),
        )
        .outerjoin(Post, Post.dataset_id == Dataset.id)
        .group_by(Dataset.id)
    )


@router.get("", response_model=list[DatasetSummary])
def list_datasets(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DatasetSummary]:
    try:
        rows = db.execute(
            _dataset_summary_statement()
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
            .offset(offset)
            .limit(limit)
        ).mappings()
        return [DatasetSummary(**row) for row in rows]
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable",
        ) from error


@router.get("/{dataset_id}", response_model=DatasetSummary)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)) -> DatasetSummary:
    try:
        row = db.execute(
            _dataset_summary_statement().where(Dataset.id == dataset_id)
        ).mappings().one_or_none()
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable",
        ) from error

    if row is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetSummary(**row)
