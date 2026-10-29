import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.main import app, get_db
from app.models import Dataset, Post

def test_upload_csv_creates_dataset_and_posts(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, test_session = api_client
    response = test_client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "observations.csv",
                "timestamp,text,source_id,external_id\n"
                "2026-10-29T10:00:00Z,Sample post,example,post-1\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "observations.csv"
    assert response.json()["rows_received"] == 1
    assert response.json()["rows_inserted"] == 1
    assert response.json()["duplicates_skipped"] == 0
    assert response.json()["status"] == "uploaded"

    with test_session() as session:
        dataset = session.scalar(select(Dataset))
        post = session.scalar(select(Post))
        assert dataset is not None
        assert dataset.row_count == 1
        assert dataset.source_type == "csv_upload"
        assert post is not None
        assert post.dataset_id == dataset.id
        assert post.external_id == "post-1"
        assert post.timestamp is not None
        assert len(post.content_hash) == 64


def test_upload_counts_and_skips_duplicate_content(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    test_client, test_session = api_client
    response = test_client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "duplicates.csv",
                "timestamp,text,source_id\n"
                "2026-10-29T10:00:00Z,Repeated text,source-a\n"
                "2026-10-29T10:05:00Z,Repeated   text,source-b\n"
                "2026-10-29T10:10:00Z,Different text,source-a\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["rows_received"] == 3
    assert response.json()["rows_inserted"] == 2
    assert response.json()["duplicates_skipped"] == 1

    with test_session() as session:
        dataset = session.scalar(select(Dataset))
        posts = session.scalars(select(Post)).all()
        assert dataset is not None
        assert dataset.row_count == 2
        assert len(posts) == 2


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("observations.txt", b"timestamp,text\n2026-01-01T00:00:00Z,post\n", "Upload a .csv file"),
        ("observations.csv", b"timestamp,source_id\n2026-01-01T00:00:00Z,source\n", "missing required columns"),
        (
            "observations.csv",
            b"timestamp,text,unknown\n2026-01-01T00:00:00Z,post,x\n",
            "unsupported columns",
        ),
        (
            "observations.csv",
            b"timestamp,text\nnot-a-date,post\n",
            "ISO 8601",
        ),
        (
            "observations.csv",
            b"timestamp,text\n2026-01-01T00:00:00Z,\n",
            "missing text",
        ),
    ],
)
def test_invalid_csv_is_rejected_without_creating_data(
    api_client: tuple[TestClient, sessionmaker[Session]],
    filename: str,
    content: bytes,
    message: str,
) -> None:
    test_client, test_session = api_client
    response = test_client.post(
        "/api/v1/datasets/upload",
        files={"file": (filename, content, "text/csv")},
    )

    assert response.status_code == 400
    assert message in response.json()["detail"]

    with test_session() as session:
        assert session.scalar(select(Dataset)) is None
        assert session.scalar(select(Post)) is None
