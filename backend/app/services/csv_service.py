import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

REQUIRED_COLUMNS = {"timestamp", "text"}
OPTIONAL_COLUMNS = {"source_id", "external_id"}
IGNORED_COLUMNS = {"dataset_label", "expected_topic"}
COLUMN_ALIASES = {
    "created_at": "timestamp",
    "date": "timestamp",
    "published_at": "timestamp",
    "content": "text",
    "message": "text",
    "platform": "source_id",
    "source": "source_id",
    "post_id": "external_id",
}
MAX_ROWS = 10_000
MAX_TEXT_LENGTH = 100_000
MAX_SOURCE_ID_LENGTH = 100
MAX_EXTERNAL_ID_LENGTH = 150


@dataclass(frozen=True)
class ParsedPosts:
    rows_received: int
    records: list[dict[str, Any]]
    duplicates_skipped: int


def normalize_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold()).strip("_")
    return COLUMN_ALIASES.get(normalized, normalized)


def get_column(row: dict[str, Any], *names: str) -> Any:
    normalized_row = {normalize_key(str(key)): value for key, value in row.items() if key is not None}
    for name in names:
        value = normalized_row.get(normalize_key(name))
        if value is not None:
            return value
    return None


def parse_timestamp(value: str | None, row_number: int) -> datetime:
    timestamp = (value or "").strip()
    if not timestamp:
        raise ValueError(f"CSV row {row_number} is missing timestamp")
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"CSV row {row_number} timestamp must be an ISO 8601 datetime"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_posts_csv(content: bytes) -> ParsedPosts:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV file must use UTF-8 encoding") from error

    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    if reader.fieldnames is None:
        raise ValueError("CSV file must include a header row")

    headers = [header.strip() if header is not None else "" for header in reader.fieldnames]
    normalized_headers = [normalize_key(header) for header in headers]
    if any(not header for header in normalized_headers):
        raise ValueError("CSV header names must be non-empty")
    if len(normalized_headers) != len(set(normalized_headers)):
        raise ValueError("CSV header names must be unique after normalization")
    reader.fieldnames = normalized_headers

    missing_columns = REQUIRED_COLUMNS - set(normalized_headers)
    if missing_columns:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(sorted(missing_columns))
        )
    unexpected_columns = (
        set(normalized_headers) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS - IGNORED_COLUMNS
    )
    if unexpected_columns:
        raise ValueError(
            "CSV contains unsupported columns: " + ", ".join(sorted(unexpected_columns))
        )

    posts: list[dict[str, Any]] = []
    seen_external_ids: set[tuple[str | None, str]] = set()
    rows_received = 0
    duplicates_skipped = 0
    try:
        for row_number, row in enumerate(reader, start=2):
            if row_number > MAX_ROWS + 1:
                raise ValueError(f"CSV file cannot contain more than {MAX_ROWS} data rows")
            if None in row:
                raise ValueError(f"CSV row {row_number} has more values than the header")
            rows_received += 1

            timestamp = parse_timestamp(get_column(row, "timestamp"), row_number)
            post_text = (get_column(row, "text") or "").strip()
            if not post_text:
                raise ValueError(f"CSV row {row_number} is missing text")
            if len(post_text) > MAX_TEXT_LENGTH:
                raise ValueError(
                    f"CSV row {row_number} text exceeds {MAX_TEXT_LENGTH} characters"
                )

            source_id = (get_column(row, "source_id") or "").strip() or None
            if source_id and len(source_id) > MAX_SOURCE_ID_LENGTH:
                raise ValueError(
                    f"CSV row {row_number} source_id exceeds {MAX_SOURCE_ID_LENGTH} characters"
                )
            external_id = (get_column(row, "external_id") or "").strip() or None
            if external_id and len(external_id) > MAX_EXTERNAL_ID_LENGTH:
                raise ValueError(
                    f"CSV row {row_number} external_id exceeds {MAX_EXTERNAL_ID_LENGTH} characters"
                )

            canonical_text = " ".join(post_text.split())
            content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()
            if external_id is not None:
                identity = (source_id, external_id)
                if identity in seen_external_ids:
                    duplicates_skipped += 1
                    continue
                seen_external_ids.add(identity)
            posts.append(
                {
                    "timestamp": timestamp,
                    "text": post_text,
                    "source_id": source_id,
                    "external_id": external_id,
                    "content_hash": content_hash,
                }
            )
    except csv.Error as error:
        raise ValueError(f"Invalid CSV: {error}") from error

    if rows_received == 0:
        raise ValueError("CSV file must contain at least one data row")
    return ParsedPosts(
        rows_received=rows_received,
        records=posts,
        duplicates_skipped=duplicates_skipped,
    )
