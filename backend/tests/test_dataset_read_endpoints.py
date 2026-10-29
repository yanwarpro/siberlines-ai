from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models import Dataset, Post


def test_list_datasets_returns_paginated_metadata_only(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    with test_session() as session:
        dataset = Dataset(
            name="Authorized collection",
            source_type="csv_upload",
            status="uploaded",
            row_count=1,
        )
        session.add(dataset)
        session.flush()
        session.add(
            Post(
                dataset_id=dataset.id,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                source_id="example",
                content_hash="hash-record-1",
                text="Private uploaded text",
            )
        )
        session.commit()

    response = client.get("/api/v1/datasets?limit=10&offset=0")

    assert response.status_code == 200
    assert len(response.json()) == 1
    record = response.json()[0]
    assert record["name"] == "Authorized collection"
    assert record["row_count"] == 1
    assert "description" not in record
    assert "posts" not in record
    assert "Private uploaded text" not in response.text


def test_get_dataset_returns_metadata_and_post_count(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    with test_session() as session:
        dataset = Dataset(
            name="Test dataset",
            source_type="csv_upload",
            status="uploaded",
            row_count=2,
        )
        session.add(dataset)
        session.flush()
        dataset_id = dataset.id
        session.add_all(
            [
                Post(
                    dataset_id=dataset_id,
                    external_id=f"record-{index}",
                    source_id="example",
                    timestamp=datetime(2026, 1, index, tzinfo=timezone.utc),
                    text="Not included in metadata endpoint",
                    content_hash=f"hash-record-{index}",
                )
                for index in (1, 2)
            ]
        )
        session.commit()

    response = client.get(f"/api/v1/datasets/{dataset_id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(dataset_id)
    assert response.json()["row_count"] == 2
    assert "posts" not in response.json()
    assert "Not included in metadata endpoint" not in response.text


def test_get_dataset_returns_404_for_missing_dataset(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get(f"/api/v1/datasets/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset not found"}


def test_list_datasets_rejects_out_of_range_limit(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get("/api/v1/datasets?limit=101")

    assert response.status_code == 422
