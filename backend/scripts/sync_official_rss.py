"""Import the approved CISA and UK NCSC RSS feeds into separate datasets."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Post, RssFeed  # noqa: E402
from app.services.rss_service import (  # noqa: E402
    RssFeedError,
    fetch_rss_feed,
    persist_rss_items,
)
import hashlib  # noqa: E402
from sqlalchemy import select  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report RSS items without storing them.",
    )
    args = parser.parse_args()

    failed = False
    with SessionLocal() as session:
        feed_ids = session.scalars(
            select(RssFeed.id)
            .where(RssFeed.enabled.is_(True))
            .order_by(RssFeed.created_at, RssFeed.id)
        ).all()
        for feed_id in feed_ids:
            feed = session.get(RssFeed, feed_id)
            if feed is None:
                print(f"SKIP {feed_id}: RSS source was removed during sync.", file=sys.stderr)
                continue
            try:
                parsed_feed = fetch_rss_feed(feed)
            except RssFeedError as error:
                print(f"ERROR {feed.name}: {error}", file=sys.stderr)
                feed.last_sync_status = "failed"
                feed.last_sync_error = str(error)[:2000]
                session.commit()
                failed = True
                continue

            dataset_id = feed.dataset_id
            existing_ids = set()
            if dataset_id:
                existing_ids = set(
                    session.scalars(
                        select(Post.external_id).where(
                            Post.dataset_id == dataset_id,
                            Post.source_id == f"rss:{feed.id}",
                            Post.external_id.is_not(None),
                        )
                    ).all()
                )
            unique_items = []
            duplicates = 0
            for item in parsed_feed.items:
                identity = hashlib.sha256(item.url.encode("utf-8")).hexdigest()
                if identity in existing_ids:
                    duplicates += 1
                else:
                    unique_items.append(item)
                    existing_ids.add(identity)

            if args.dry_run:
                inserted = len(unique_items)
            else:
                result = persist_rss_items(session, feed, parsed_feed)
                inserted = result.items_inserted
                duplicates = result.duplicates_skipped
            action = "would insert" if args.dry_run else "inserted"
            print(
                f"{feed.name}: received {len(parsed_feed.items)}; {action} "
                f"{inserted}; skipped {duplicates} duplicates and "
                f"{parsed_feed.invalid_items} invalid/over-limit items; "
                f"dataset={dataset_id or 'not created'}."
            )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
