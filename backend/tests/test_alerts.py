from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models import Alert, Dataset, Post
from app.services.alert_service import build_fingerprint
from app.services.csv_service import parse_posts_csv

SAMPLE_DATASET = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "siberlens_dummy_dataset.csv"
)

def _content_hash(text: str) -> str:
    """Mirror the canonical hash that `csv_service` assigns to ingested posts."""
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()

def _insert_sample_dataset(session_factory: sessionmaker[Session]) -> str:
    parsed = parse_posts_csv(SAMPLE_DATASET.read_bytes())
    dataset_id = uuid4()
    with session_factory() as session:
        session.add(
            Dataset(
                id=dataset_id,
                name="Alert integration dataset",
                source_type="csv_upload",
                row_count=len(parsed.records),
                status="uploaded",
            )
        )
        session.add_all(
            Post(dataset_id=dataset_id, **row) for row in parsed.records
        )
        session.commit()
    return str(dataset_id)

def _run_analysis(client: TestClient, dataset_id: str) -> dict:
    response = client.post(f"/api/v1/datasets/{dataset_id}/analyses")
    assert response.status_code == 201, response.text
    return response.json()

def _stored_alerts(session_factory: sessionmaker[Session]) -> list[Alert]:
    with session_factory() as session:
        return session.query(Alert).order_by(Alert.created_at).all()

def test_analysis_creates_persisted_alert_with_finding_links(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)

    result = _run_analysis(client, dataset_id)

    alerts = _stored_alerts(test_session)
    assert len(alerts) == 1
    alert = alerts[0]
    assert str(alert.analysis_id) == result["id"]
    assert str(alert.dataset_id) == dataset_id
    assert alert.status == "new"
    assert alert.severity in {"high", "medium"}
    assert alert.fingerprint is not None and len(alert.fingerprint) == 64
    assert alert.detection_interval_start is not None
    assert alert.detected_at is not None
    assert alert.narrative_cluster_id is not None
    assert alert.episode_id is not None
    assert alert.status_history_json == []
    assert alert.analyst_notes_json == []

def test_rerunning_analysis_does_not_duplicate_the_alert(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)

    first = _run_analysis(client, dataset_id)
    second = _run_analysis(client, dataset_id)
    third = _run_analysis(client, dataset_id)

    assert first["id"] != second["id"] != third["id"]
    alerts = _stored_alerts(test_session)
    assert len(alerts) == 1
    # The alert keeps pointing at the analysis that first detected the finding.
    assert str(alerts[0].analysis_id) == first["id"]

def test_reloading_pages_never_creates_alerts(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)

    for _ in range(3):
        assert client.get("/api/v1/alerts").status_code == 200
        assert client.get("/api/v1/alerts/summary").status_code == 200
        assert client.get(f"/api/v1/analyses/{result['id']}").status_code == 200
        assert client.get(f"/api/v1/datasets/{dataset_id}/analyses").status_code == 200

    assert len(_stored_alerts(test_session)) == 1

def test_fingerprint_ignores_analysis_identity(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)

    alert = _stored_alerts(test_session)[0]
    interval_start = datetime.fromisoformat(
        result["metrics_json"]["volume_review"]["interval_start"]
    )
    expected = build_fingerprint(
        alert.dataset_id,
        alert.narrative_key,
        interval_start,
    )
    assert alert.fingerprint == expected

    # A different detection interval must produce a different fingerprint.
    other = build_fingerprint(
        alert.dataset_id,
        alert.narrative_key,
        interval_start + timedelta(hours=1),
    )
    assert other != alert.fingerprint

def test_alerts_endpoint_lists_and_filters(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)

    listing = client.get("/api/v1/alerts")
    assert listing.status_code == 200
    page = listing.json()
    assert page["total"] == 1
    assert page["limit"] == 25
    assert page["offset"] == 0
    item = page["items"][0]
    assert item["dataset_id"] == dataset_id
    assert item["dataset_name"] == "Alert integration dataset"
    assert item["analysis_id"] == result["id"]
    assert item["status"] == "new"

    assert client.get(f"/api/v1/alerts?status=new").json()["total"] == 1
    assert client.get("/api/v1/alerts?status=resolved").json()["total"] == 0
    assert (
        client.get(f"/api/v1/alerts?dataset_id={dataset_id}").json()["total"] == 1
    )
    assert (
        client.get(f"/api/v1/alerts?dataset_id={uuid4()}").json()["total"] == 0
    )
    assert (
        client.get(f"/api/v1/alerts?severity={item['severity']}").json()["total"] == 1
    )
    assert client.get("/api/v1/alerts?severity=critical").json()["total"] == 0

    invalid = client.get("/api/v1/alerts?status=not_a_status")
    assert invalid.status_code == 422
    assert "Allowed values" in invalid.json()["detail"]

def test_alerts_summary_counts_real_records(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    _run_analysis(client, dataset_id)

    summary = client.get("/api/v1/alerts/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total"] == 1
    assert body["new"] == 1
    assert body["open_total"] == 1
    assert body["resolved"] == 0
    assert body["dismissed"] == 0
    assert body["high_priority"] + body["medium_priority"] == 1

def test_alert_detail_exposes_evidence_and_originating_analysis(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)
    alert_id = result["alerts"][0]["id"]

    detail = client.get(f"/api/v1/alerts/{alert_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["analysis_id"] == result["id"]
    assert body["dataset_id"] == dataset_id
    assert body["dataset_name"] == "Alert integration dataset"
    assert body["explanation"]
    assert body["observed_count"] == 25
    assert body["baseline_count"] >= 0
    interval_start = datetime.fromisoformat(
        body["detection_interval_start"].replace("Z", "+00:00")
    )
    interval_end = datetime.fromisoformat(
        body["detection_interval_end"].replace("Z", "+00:00")
    )
    assert interval_start.tzinfo is not None
    assert interval_end.tzinfo is not None
    assert interval_start < interval_end
    assert body["evidence_json"]
    assert all(
        entry["post_id"] and entry["timestamp"] and entry["text"]
        for entry in body["evidence_json"]
    )

    assert client.get(f"/api/v1/alerts/{uuid4()}").status_code == 404

def test_analysis_scoped_alert_endpoint(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)

    scoped = client.get(f"/api/v1/analyses/{result['id']}/alerts")
    assert scoped.status_code == 200
    assert [alert["id"] for alert in scoped.json()] == [
        result["alerts"][0]["id"]
    ]
    assert client.get(f"/api/v1/analyses/{uuid4()}/alerts").status_code == 404

def test_status_transitions_persist_and_are_recorded(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)
    alert_id = result["alerts"][0]["id"]

    for status in ("pending_review", "under_review", "resolved"):
        response = client.patch(
            f"/api/v1/alerts/{alert_id}/status",
            json={"status": status, "note": f"moved to {status}"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status

    detail = client.get(f"/api/v1/alerts/{alert_id}").json()
    assert detail["status"] == "resolved"
    history = detail["status_history_json"]
    assert [entry["to_status"] for entry in history] == [
        "pending_review",
        "under_review",
        "resolved",
    ]
    assert [entry["from_status"] for entry in history] == [
        "new",
        "pending_review",
        "under_review",
    ]
    assert all(
        datetime.fromisoformat(entry["recorded_at"].replace("Z", "+00:00")).tzinfo
        is not None
        for entry in history
    )

    # Resolved alerts stay visible and queryable for auditability.
    assert client.get("/api/v1/alerts?status=resolved").json()["total"] == 1
    summary = client.get("/api/v1/alerts/summary").json()
    assert summary["resolved"] == 1
    assert summary["open_total"] == 0

def test_dismissed_alerts_are_preserved(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)
    alert_id = result["alerts"][0]["id"]

    response = client.patch(
        f"/api/v1/alerts/{alert_id}/status",
        json={"status": "dismissed", "note": "not actionable"},
    )
    assert response.status_code == 200

    listing = client.get("/api/v1/alerts?status=dismissed").json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == alert_id
    assert client.get(f"/api/v1/alerts/{alert_id}").status_code == 200

def test_invalid_status_is_rejected(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)
    alert_id = result["alerts"][0]["id"]

    response = client.patch(
        f"/api/v1/alerts/{alert_id}/status",
        json={"status": "archived"},
    )
    assert response.status_code == 422
    assert client.get(f"/api/v1/alerts/{alert_id}").json()["status"] == "new"

def test_alert_notes_are_recorded_separately_from_findings(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = _insert_sample_dataset(test_session)
    result = _run_analysis(client, dataset_id)
    alert_id = result["alerts"][0]["id"]

    response = client.post(
        f"/api/v1/alerts/{alert_id}/notes",
        json={"body": "Verified against the source post."},
    )
    assert response.status_code == 201, response.text
    note = response.json()
    assert note["body"] == "Verified against the source post."
    assert datetime.fromisoformat(
        note["created_at"].replace("Z", "+00:00")
    ).tzinfo is not None

    detail = client.get(f"/api/v1/alerts/{alert_id}").json()
    assert len(detail["analyst_notes_json"]) == 1
    assert detail["analyst_notes_json"][0]["note_id"] == note["note_id"]
    # Automated evidence is untouched by analyst input.
    assert detail["evidence_json"]
    assert detail["explanation"]

    assert (
        client.post(
            f"/api/v1/alerts/{alert_id}/notes", json={"body": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/alerts/{uuid4()}/notes", json={"body": "orphan"}
        ).status_code
        == 404
    )

def test_dataset_without_a_spike_creates_no_alert(
    api_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, test_session = api_client
    dataset_id = uuid4()
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with test_session() as session:
        session.add(
            Dataset(
                id=dataset_id,
                name="Flat dataset",
                source_type="csv_upload",
                row_count=3,
                status="uploaded",
            )
        )
        session.add_all(
            Post(
                dataset_id=dataset_id,
                timestamp=start + timedelta(hours=index),
                source_id=f"src-{index}",
                text=f"Calm unrelated note number {index} about the weather",
                content_hash=_content_hash(
                    f"Calm unrelated note number {index} about the weather"
                ),
                external_id=f"flat-{index}",
            )
            for index in range(3)
        )
        session.commit()

    result = _run_analysis(client, str(dataset_id))

    assert result["alerts"] == []
    assert _stored_alerts(test_session) == []
    assert client.get("/api/v1/alerts").json()["total"] == 0
