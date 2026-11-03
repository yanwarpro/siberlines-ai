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
3. Links the alert to the narrative cluster / temporal episode that the same
   analysis flagged as containing a volume spike.
4. Computes the fingerprint with the same function the API uses
   (``app.services.alert_service.build_fingerprint``), so a later re-run of the
   analysis collides with the backfilled row instead of inserting a duplicate.

Because the fingerprint is unique, several historical alerts that describe the
*same* finding collapse to one identity. The earliest row keeps the fingerprint;
the rest are marked ``dismissed`` with an audit note naming the surviving alert.
Nothing is deleted, so the history stays auditable.

The script is idempotent: re-running it finds no NULL fingerprints and reports
that there is nothing to do.

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

def _spike_linkage(metrics: dict[str, Any]) -> tuple[str | None, str | None]:
    """First narrative cluster / episode the analysis flagged as spiking."""
    for narrative in metrics.get("narratives") or []:
        for episode in narrative.get("episodes") or []:
            if episode.get("volume_spike_detected"):
                return (
                    episode.get("narrative_cluster_id") or narrative.get("narrative_cluster_id"),
                    episode.get("episode_id"),
                )
    return None, None

def backfill(dry_run: bool) -> int:
    with SessionLocal() as session:
        pending = session.scalars(
            select(Alert).where(Alert.fingerprint.is_(None)).order_by(Alert.created_at)
        ).all()
        if not pending:
            print("No alerts are missing a fingerprint. Nothing to backfill.")
            return 0

        print(f"Found {len(pending)} alert(s) without a fingerprint.")

        keepers: dict[str, Alert] = {}
        updated = 0
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

            cluster_id, episode_id = _spike_linkage(metrics)
            dataset_id = analysis.dataset_id or alert.dataset_id
            fingerprint = build_fingerprint(dataset_id, alert.narrative_key, start)

            keeper = keepers.get(fingerprint)
            if keeper is None:
                keepers[fingerprint] = alert
                alert.dataset_id = dataset_id
                alert.narrative_cluster_id = cluster_id
                alert.episode_id = episode_id
                alert.detection_interval_start = start
                alert.detection_interval_end = end
                alert.detected_at = start
                alert.fingerprint = fingerprint
                updated += 1
                print(
                    f"  KEEP {alert.id} fingerprint={fingerprint[:12]}... "
                    f"window={start.isoformat()} ({source})"
                )
            else:
                alert.status = "dismissed"
                alert.status_history_json = [
                    *(alert.status_history_json or []),
                    {
                        "event_id": f"backfill-{alert.id}",
                        "from_status": "new",
                        "to_status": "dismissed",
                        "note": DUPLICATE_NOTE.format(keeper_id=keeper.id),
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        "actor": "migration",
                    },
                ]
                alert.updated_at = datetime.now(timezone.utc)
                dismissed += 1
                print(f"  DUP  {alert.id} duplicates {keeper.id} -> dismissed")

        if dry_run:
            session.rollback()
            print(
                f"\nDry run: {updated} would be backfilled, {dismissed} would be "
                f"dismissed as duplicates, {unresolved} could not be resolved. "
                "No changes were committed."
            )
        else:
            session.commit()
            print(
                f"\nBackfilled {updated} alert(s); dismissed {dismissed} duplicate(s); "
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
