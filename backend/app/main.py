from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api.datasets import router as datasets_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Dataset, Post
from app.services.csv_service import parse_posts_csv

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

settings = get_settings()

app = FastAPI(title="SIBERLENS AI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router, prefix="/api/v1", tags=["health"])


@app.post("/api/v1/datasets/upload", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str | None = Form(default=None, max_length=200),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    try:
        if not file.filename or Path(file.filename).suffix.casefold() != ".csv":
            raise HTTPException(status_code=400, detail="Upload a .csv file")

        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV file exceeds the 5 MiB limit")

        try:
            posts = parse_posts_csv(content)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        dataset_name = (name or Path(file.filename).stem).strip()
        if not dataset_name:
            raise HTTPException(status_code=400, detail="Dataset name cannot be empty")

        dataset = Dataset(name=dataset_name, source="csv_upload", status="uploaded")
        with db.begin():
            db.add(dataset)
            db.flush()
            db.add_all(Post(dataset_id=dataset.id, **post_data) for post_data in posts)
            db.flush()
    finally:
        await file.close()

    return {
        "dataset_id": dataset.id,
        "name": dataset.name,
        "status": dataset.status,
        "post_count": len(posts),
    }


app.include_router(datasets_router, prefix="/api/v1")
