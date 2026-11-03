"""Alert persistence, deduplication, and review-workflow helpers."""

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert

def _interval_token(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    moment = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()

def build_fingerprint(
    dataset_id: UUID | None,
    narrative_key: str,
    detection_interval_start: datetime | None,
) -> str:
    """Derive a stable identity for a finding.

    The fingerprint deliberately excludes ``analysis_id``: re-running analysis on
    the same dataset produces the same finding, and re-running must not create a
    second alert. Including the detection interval keeps genuinely different
    spikes in the same dataset distinct.
    """
    material = "|".join(
        (
            str(dataset_id) if dataset_id is not None else "no-dataset",
            narrative_key,
            _interval_token(detection_interval_start),
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()

def build_alert(analysis_id: UUID, analysis_dataset_id: UUID, alert_data: dict[str, Any]) -> Alert:
    """Construct an unsaved Alert from the analysis engine's alert payload."""
    dataset_id = alert_data.get("dataset_id") or analysis_dataset_id
    narrative_key = alert_data["narrative_key"]
    interval_start = alert_data.get("detection_interval_start")
    return Alert(
        analysis_id=analysis_id,
        dataset_id=dataset_id,
        narrative_key=narrative_key,
        narrative_cluster_id=alert_data.get("narrative_cluster_id"),
        episode_id=alert_data.get("episode_id"),
        severity=alert_data["severity"],
        baseline_count=alert_data["baseline_count"],
        observed_count=alert_data["observed_count"],
        evidence_json=alert_data["evidence_json"],
        explanation=alert_data.get("explanation"),
        status="new",
        detection_interval_start=interval_start,
        detection_interval_end=alert_data.get("detection_interval_end"),
        detected_at=alert_data.get("detected_at") or interval_start,
        fingerprint=build_fingerprint(dataset_id, narrative_key, interval_start),
        status_history_json=[],
        analyst_notes_json=[],
    )

def find_alert_by_fingerprint(db: Session, fingerprint: str) -> Alert | None:
    return db.scalar(select(Alert).where(Alert.fingerprint == fingerprint))

def record_alert(
    db: Session,
    analysis_id: UUID,
    analysis_dataset_id: UUID,
    alert_data: dict[str, Any],
) -> tuple[Alert, bool]:
    """Persist an alert unless an identical finding already exists.

    Returns ``(alert, created)``. When a duplicate is found the existing row is
    returned untouched so the caller can still reference a real alert id; the
    analysis that re-detected the finding is not overwritten.
    """
    candidate = build_alert(analysis_id, analysis_dataset_id, alert_data)
    existing = find_alert_by_fingerprint(db, candidate.fingerprint or "")
    if existing is not None:
        return existing, False
    db.add(candidate)
    db.flush()
    return candidate, True

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def _status_entry(from_status: str, to_status: str, note: str | None) -> dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "from_status": from_status,
        "to_status": to_status,
        "note": note,
        "recorded_at": _utc_now().isoformat(),
        "actor": "analyst",
    }

def apply_status_change(
    alert: Alert,
    new_status: str,
    note: str | None,
) -> Alert:
    """Append a status transition. Callers validate the status value."""
    previous = alert.status
    if previous == new_status and not note:
        return alert
    alert.status = new_status
    alert.status_history_json = [
        *(alert.status_history_json or []),
        _status_entry(previous, new_status, note),
    ]
    alert.updated_at = _utc_now()
    return alert

def add_analyst_note(alert: Alert, body: str) -> dict[str, Any]:
    note = {
        "note_id": str(uuid4()),
        "body": body,
        "created_at": _utc_now().isoformat(),
        "actor": "analyst",
    }
    alert.analyst_notes_json = [*(alert.analyst_notes_json or []), note]
    alert.updated_at = _utc_now()
    return note
