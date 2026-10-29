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
                "external_id,platform,text,author,published_at\n"
                "post-1,example,Sample post,analyst,2026-10-29T10:00:00Z\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "observations"
    assert response.json()["status"] == "uploaded"
    assert response.json()["post_count"] == 1

    with test_session() as session:
        dataset = session.scalar(select(Dataset))
        post = session.scalar(select(Post))
        assert dataset is not None
        assert post is not None
        assert post.dataset_id == dataset.id
        assert post.external_id == "post-1"
        assert post.published_at is not None


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("observations.txt", b"external_id,platform\npost-1,example\n", "Upload a .csv file"),
        ("observations.csv", b"external_id\npost-1\n", "missing required columns"),
        (
            "observations.csv",
            b"external_id,platform\npost-1,example\npost-1,example\n",
            "duplicate external_id",
        ),
        (
            "observations.csv",
            b"external_id,platform,published_at\npost-1,example,not-a-date\n",
            "ISO 8601",
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
