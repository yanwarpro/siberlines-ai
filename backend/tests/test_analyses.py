from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Analysis, Dataset, Post
from app.services.csv_service import parse_posts_csv

SAMPLE_DATASET = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "siberlens_dummy_dataset.csv"
)


def _insert_posts(
    session_factory: sessionmaker[Session],
    rows: list[dict],
) -> str:
    dataset_id = uuid4()
    with session_factory() as session:
        dataset = Dataset(
            id=dataset_id,
            name="Synthetic analysis test",
            source_type="csv_upload",
            row_count=len(rows),
            status="uploaded",
        )
        session.add(dataset)
        session.add_all(
            Post(dataset_id=dataset_id, **row)
            for row in rows
        )
        session.commit()
    return str(dataset_id)


def test_analysis_runs_on_supplied_dataset_and_can_be_reloaded(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    parsed = parse_posts_csv(SAMPLE_DATASET.read_bytes())
    dataset_id = _insert_posts(test_session, parsed.records)

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 201
    result = response.json()
    assert result["status"] == "completed"
    metrics = result["metrics_json"]
    assert metrics["summary"]["post_count"] == 78
    assert metrics["summary"]["alert_count"] == 1
    assert metrics["summary"]["baseline_sufficient"] is True
    assert metrics["volume_review"]["interval_start"] == "2026-10-28T14:00:00+00:00"
    assert metrics["volume_review"]["interval_end"] == "2026-10-28T15:00:00+00:00"
    assert metrics["volume_review"]["observed_count"] == 25
    assert metrics["volume_review"]["baseline_mean"] < 1
    assert metrics["volume_review"]["baseline_hours"] >= 24
    assert len(metrics["trend"]) > 24
    assert max(point["count"] for point in metrics["trend"]) == 25
    assert any("Jembatan Kenanga" in group["representative_text"] for group in metrics["narratives"])
    assert result["alerts"][0]["observed_count"] == 25
    alert_evidence_ids = {
        evidence["post_id"] for evidence in result["alerts"][0]["evidence_json"]
    }
    assert any(
        alert_evidence_ids.intersection(
            evidence["post_id"] for evidence in group["evidence"]
        )
        for group in metrics["narratives"]
    )
    assert "expected_topic" not in str(metrics)
    assert "dataset_label" not in str(metrics)

    analysis_id = result["id"]
    reloaded = client.get(f"/api/v1/analyses/{analysis_id}")
    history = client.get(f"/api/v1/datasets/{dataset_id}/analyses")
    assert reloaded.status_code == 200
    assert reloaded.json() == result
    assert history.status_code == 200
    assert [analysis["id"] for analysis in history.json()] == [analysis_id]

    with test_session() as session:
        saved = session.get(Analysis, UUID(analysis_id))
        assert saved is not None
        assert saved.metrics_json["summary"]["post_count"] == 78


def test_short_dataset_does_not_create_spike_alert(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    parsed = parse_posts_csv(
        b"external_id,timestamp,source_id,text\n"
        b"one,2026-10-28T10:00:00Z,simulated,First sample report\n"
        b"two,2026-10-28T10:05:00Z,simulated,Second sample report\n"
        b"three,2026-10-28T10:10:00Z,simulated,Third sample report\n"
    )
    dataset_id = _insert_posts(test_session, parsed.records)

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 201
    result = response.json()
    assert result["alerts"] == []
    assert result["metrics_json"]["summary"]["alert_count"] == 0
    assert result["metrics_json"]["summary"]["baseline_sufficient"] is False
    assert result["metrics_json"]["volume_review"] is None
    assert any("baseline" in warning for warning in result["metrics_json"]["warnings"])


def test_analysis_rejects_missing_dataset(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.post(f"/api/v1/datasets/{uuid4()}/analyses")

    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset not found"}


def test_analysis_rejects_dataset_without_posts(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    with test_session() as session:
        dataset = Dataset(name="Empty dataset", row_count=0)
        session.add(dataset)
        session.commit()
        dataset_id = dataset.id

    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")

    assert response.status_code == 422
    assert response.json() == {"detail": "Cannot analyze a dataset with no posts"}


def test_list_analysis_returns_404_for_missing_dataset(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api_client

    response = client.get(f"/api/v1/datasets/{uuid4()}/analyses")

    assert response.status_code == 404
