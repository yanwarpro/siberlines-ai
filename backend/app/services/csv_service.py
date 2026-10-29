import csv
import io
from datetime import datetime, timezone
from typing import Any

REQUIRED_COLUMNS = {"external_id", "platform"}
OPTIONAL_COLUMNS = {"text", "author", "published_at"}
MAX_ROWS = 10_000
MAX_EXTERNAL_ID_LENGTH = 255
MAX_PLATFORM_LENGTH = 80
MAX_AUTHOR_LENGTH = 255


def parse_posts_csv(content: bytes) -> list[dict[str, Any]]:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV file must use UTF-8 encoding") from error

    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if reader.fieldnames is None:
        raise ValueError("CSV file must include a header row")

    headers = [header.strip() for header in reader.fieldnames if header is not None]
    if len(headers) != len(reader.fieldnames) or len(headers) != len(set(headers)):
        raise ValueError("CSV header names must be non-empty and unique")
    reader.fieldnames = headers
    missing_columns = REQUIRED_COLUMNS - set(headers)
    if missing_columns:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(sorted(missing_columns))
        )
    unexpected_columns = set(headers) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
    if unexpected_columns:
        raise ValueError(
            "CSV contains unsupported columns: " + ", ".join(sorted(unexpected_columns))
        )

    posts: list[dict[str, Any]] = []
    seen_external_ids: set[str] = set()
    try:
        for row_number, row in enumerate(reader, start=2):
            if row_number > MAX_ROWS + 1:
                raise ValueError(f"CSV file cannot contain more than {MAX_ROWS} data rows")
            if None in row:
                raise ValueError(f"CSV row {row_number} has more values than the header")

            external_id = (row.get("external_id") or "").strip()
            platform = (row.get("platform") or "").strip()
            if not external_id:
                raise ValueError(f"CSV row {row_number} is missing external_id")
            if len(external_id) > MAX_EXTERNAL_ID_LENGTH:
                raise ValueError(
                    f"CSV row {row_number} external_id exceeds {MAX_EXTERNAL_ID_LENGTH} characters"
                )
            if external_id in seen_external_ids:
                raise ValueError(f"CSV contains duplicate external_id on row {row_number}")
            if not platform:
                raise ValueError(f"CSV row {row_number} is missing platform")
            if len(platform) > MAX_PLATFORM_LENGTH:
                raise ValueError(
                    f"CSV row {row_number} platform exceeds {MAX_PLATFORM_LENGTH} characters"
                )

            author = (row.get("author") or "").strip() or None
            if author and len(author) > MAX_AUTHOR_LENGTH:
                raise ValueError(
                    f"CSV row {row_number} author exceeds {MAX_AUTHOR_LENGTH} characters"
                )

            published_at_value = (row.get("published_at") or "").strip()
            published_at = None
            if published_at_value:
                try:
                    published_at = datetime.fromisoformat(
                        published_at_value.replace("Z", "+00:00")
                    )
                except ValueError as error:
                    raise ValueError(
                        f"CSV row {row_number} published_at must be an ISO 8601 datetime"
                    ) from error
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=timezone.utc)

            seen_external_ids.add(external_id)
            posts.append(
                {
                    "external_id": external_id,
                    "platform": platform,
                    "text": (row.get("text") or "").strip() or None,
                    "author": author,
                    "published_at": published_at,
                    "raw_payload": row,
                }
            )
    except csv.Error as error:
        raise ValueError(f"Invalid CSV: {error}") from error

    if not posts:
        raise ValueError("CSV file must contain at least one data row")
    return posts
