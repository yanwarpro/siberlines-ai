"""Backfill review-workflow metadata for alerts created before migration 0004.

Why this script exists:
Migration ``0004_alert_review_workflow`` added the ``fingerprint`` column and a
unique index on it, but deliberately left every historical row NULL: a
fingerprint can only be derived from the detection interval, and fabricating one
inside a migration would silently invent data. This script recomputes each
legacy alert's true identity from the analysis run that produced it.

What it does, per alert whose ``fingerprint`` is still NULL:

1. Resolves ``dataset_id`` from the parent analysis.
2. Reads the detection window from ``analyses.metrics_json["volume_review"]``,
   which is where the engine recorded it. When that key is absent the window is
   derived from the alert's own evidence timestamps and the gap is reported.
3. Links the alert to a spike episode from the same analysis only when the
   alert's stored evidence post IDs identify one episode unambiguously.
4. Computes the fingerprint with the same function the API uses
   (``app.services.alert_service.build_fingerprint``). If another row already
   owns that fingerprint, the legacy row remains fingerprint-less and is
   retained as a duplicate audit record.

Because the fingerprint is unique, several historical alerts that describe the
*same* finding collapse to one identity. The earliest row keeps the fingerprint;
the rest are marked ``dismissed`` with an audit note naming the surviving alert.
Nothing is deleted, so the history stays auditable.

The script is idempotent. Rows that are known duplicates remain fingerprint-less
so the unique index has a single owner; subsequent runs verify those rows without
changing their status or adding repeated audit entries.

Usage (from the ``backend`` directory):
    python scripts/backfill_alert_fingerprints.py --dry-run
    python scripts/backfill_alert_fingerprints.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models import Alert, Analysis  # noqa: E402
from app.services.alert_service import build_fingerprint  # noqa: E402

DUPLICATE_NOTE = (
    "Duplicate of alert {keeper_id}. Marked dismissed during the migration to "
    "fingerprint-based deduplication; the original row is preserved for audit."
)

def _parse_moment(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)

def _interval_from_metrics(metrics: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    review = metrics.get("volume_review") or {}
    return (
        _parse_moment(review.get("interval_start")),
        _parse_moment(review.get("interval_end")),
    )

def _interval_from_evidence(evidence: list[Any]) -> tuple[datetime | None, datetime | None]:
    """Fallback: the hour containing the earliest evidence post."""
    moments = [
        moment
        for moment in (
            _parse_moment(entry.get("timestamp"))
            for entry in evidence
            if isinstance(entry, dict)
        )
        if moment is not None
    ]
    if not moments:
        return None, None
    start = min(moments).replace(minute=0, second=0, microsecond=0)
    return start, start + timedelta(hours=1)

def _spike_linkage(
    metrics: dict[str, Any],
    evidence: list[Any],
    interval_start: datetime,
    interval_end: datetime | None,
) -> tuple[str | None, str | None]:
    """Return a spike episode only when stored evidence identifies it uniquely."""
    evidence_ids = {
        entry.get("post_id")
        for entry in evidence
        if isinstance(entry, dict) and entry.get("post_id")
    }
    if not evidence_ids:
        return None, None

    candidates: list[tuple[int, str, str]] = []
    for narrative in metrics.get("narratives") or []:
        for episode in narrative.get("episodes") or []:
            if not episode.get("volume_spike_detected"):
                continue
            episode_start = _parse_moment(episode.get("episode_start"))
            episode_end = _parse_moment(episode.get("episode_end"))
            if episode_start is None or episode_end is None:
                continue
            if interval_end is not None and episode_start >= interval_end:
                continue
            if episode_end < interval_start:
                continue

            overlap = len(evidence_ids & set(episode.get("evidence_post_ids") or []))
            if overlap < 2:
                continue
            cluster_id = episode.get("narrative_cluster_id") or narrative.get("id")
            episode_id = episode.get("episode_id")
            if cluster_id and episode_id:
                candidates.append((overlap, cluster_id, episode_id))

    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None, None
    return candidates[0][1], candidates[0][2]

def _has_duplicate_history(alert: Alert) -> bool:
    entries = [*(alert.status_history_json or []), *(alert.analyst_notes_json or [])]
    return any(
        "duplicate of alert" in str(entry.get("note", "")).lower()
        for entry in entries
        if isinstance(entry, dict)
    )

def backfill(dry_run: bool) -> int:
    with SessionLocal() as session:
        existing_fingerprints = {
            alert.fingerprint: alert
            for alert in session.scalars(
                select(Alert)
                .where(Alert.fingerprint.is_not(None))
                .order_by(Alert.created_at, Alert.id)
            ).all()
            if alert.fingerprint
        }
        pending = session.scalars(
            select(Alert).where(Alert.fingerprint.is_(None)).order_by(Alert.created_at)
        ).all()
        if not pending:
            print("No legacy alerts need fingerprint reconciliation.")
            return 0

        print(f"Found {len(pending)} alert(s) without a fingerprint.")

        keepers = dict(existing_fingerprints)
        metadata_updated = 0
        fingerprints_added = 0
        dismissed = 0
        unresolved = 0

        for alert in pending:
            analysis = session.get(Analysis, alert.analysis_id)
            if analysis is None:
                print(f"  SKIP {alert.id}: parent analysis is missing.")
                unresolved += 1
                continue

            metrics = analysis.metrics_json or {}
            start, end = _interval_from_metrics(metrics)
            source = "metrics_json.volume_review"
            if start is None:
                start, end = _interval_from_evidence(alert.evidence_json or [])
                source = "evidence_json (derived)"
            if start is None:
                print(f"  SKIP {alert.id}: no detection window can be recovered.")
                unresolved += 1
                continue

            dataset_id = analysis.dataset_id or alert.dataset_id
            fingerprint = build_fingerprint(dataset_id, alert.narrative_key, start)
            cluster_id, episode_id = _spike_linkage(
                metrics,
                alert.evidence_json or [],
                start,
                end,
            )

            keeper = keepers.get(fingerprint)
            metadata_changed = False
            if alert.dataset_id != dataset_id:
                alert.dataset_id = dataset_id
                metadata_changed = True
            if alert.detection_interval_start is None:
                alert.detection_interval_start = start
                metadata_changed = True
            if alert.detection_interval_end is None and end is not None:
                alert.detection_interval_end = end
                metadata_changed = True
            if alert.detected_at is None:
                alert.detected_at = start
                metadata_changed = True
            if not alert.narrative_cluster_id and cluster_id:
                alert.narrative_cluster_id = cluster_id
                metadata_changed = True
            if not alert.episode_id and episode_id:
                alert.episode_id = episode_id
                metadata_changed = True

            if keeper is not None:
                if alert.status != "dismissed":
                    previous_status = alert.status
                    alert.status = "dismissed"
                    alert.status_history_json = [
                        *(alert.status_history_json or []),
                        {
                            "event_id": f"backfill-{alert.id}",
                            "from_status": previous_status,
                            "to_status": "dismissed",
                            "note": DUPLICATE_NOTE.format(keeper_id=keeper.id),
                            "recorded_at": datetime.now(timezone.utc).isoformat(),
                            "actor": "migration",
                        },
                    ]
                    alert.updated_at = datetime.now(timezone.utc)
                    dismissed += 1
                    metadata_changed = True
                elif not _has_duplicate_history(alert):
                    alert.status_history_json = [
                        *(alert.status_history_json or []),
                        {
                            "event_id": f"backfill-{alert.id}",
                            "from_status": alert.status,
                            "to_status": alert.status,
                            "note": DUPLICATE_NOTE.format(keeper_id=keeper.id),
                            "recorded_at": datetime.now(timezone.utc).isoformat(),
                            "actor": "migration",
                        },
                    ]
                    alert.updated_at = datetime.now(timezone.utc)
                    metadata_changed = True
                if metadata_changed:
                    alert.updated_at = datetime.now(timezone.utc)
                metadata_updated += int(metadata_changed)
                print(
                    f"  DUP  {alert.id} already represented by {keeper.id}; "
                    f"episode={'linked' if alert.episode_id else 'not established'}"
                )
                continue

            keepers[fingerprint] = alert
            alert.narrative_cluster_id = cluster_id or alert.narrative_cluster_id
            alert.episode_id = episode_id or alert.episode_id
            alert.fingerprint = fingerprint
            fingerprints_added += 1
            metadata_updated += 1
            alert.updated_at = datetime.now(timezone.utc)
            print(
                f"  KEEP {alert.id} fingerprint={fingerprint[:12]}... "
                f"window={start.isoformat()} ({source}); "
                f"episode={'linked' if episode_id else 'not established'}"
            )

        if dry_run:
            session.rollback()
            print(
                f"\nDry run: {metadata_updated} row(s) would receive metadata, "
                f"{fingerprints_added} fingerprint(s) would be added, "
                f"{dismissed} alert(s) would be dismissed as duplicates, "
                f"{unresolved} could not be resolved. "
                "No changes were committed."
            )
        else:
            session.commit()
            print(
                f"\nUpdated metadata on {metadata_updated} alert(s); added "
                f"{fingerprints_added} fingerprint(s); dismissed {dismissed} "
                f"duplicate(s); "
                f"{unresolved} left unresolved."
            )
        return 0 if unresolved == 0 else 1

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the planned changes without committing them.",
    )
    args = parser.parse_args()
    return backfill(args.dry_run)

if __name__ == "__main__":
    raise SystemExit(main())
