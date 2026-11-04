"""Safe fetching and persistence for analyst-managed RSS sources."""

from __future__ import annotations

import hashlib
import html
import http.client
import ipaddress
import re
import socket
import ssl
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.orm import Session

from app.models import Dataset, Post, RssFeed

MAX_FEED_BYTES = 4 * 1024 * 1024
MAX_FEED_ITEMS = 100
MAX_DESCRIPTION_LENGTH = 500
REQUEST_TIMEOUT_SECONDS = 15
_SPACE_PATTERN = re.compile(r"\s+")


@dataclass(frozen=True)
class RssItem:
    title: str
    description: str
    url: str
    published_at: datetime

    @property
    def text(self) -> str:
        return f"{self.title}\n\n{self.description}" if self.description else self.title


@dataclass(frozen=True)
class ParsedRssFeed:
    items: list[RssItem]
    invalid_items: int


@dataclass(frozen=True)
class RssSyncResult:
    dataset_id: UUID
    items_received: int
    items_inserted: int
    duplicates_skipped: int
    invalid_items: int


class RssFeedError(ValueError):
    """Raised when an RSS source cannot be safely fetched or parsed."""


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, pinned_ip: str, timeout: int) -> None:
        super().__init__(hostname, 443, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = pinned_ip

    def connect(self) -> None:
        raw_socket = socket.create_connection(
            (self.pinned_ip, self.port),
            timeout=self.timeout,
            source_address=self.source_address,
        )
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _child_text(element: ET.Element, *names: str) -> str:
    wanted = {name.casefold() for name in names}
    for child in element:
        if _local_name(child.tag) in wanted:
            return "".join(child.itertext()).strip()
    return ""


def _plain_text(value: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html.unescape(value))
    extractor.close()
    return _SPACE_PATTERN.sub(" ", " ".join(extractor.parts)).strip()


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        timestamp = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _resolve_public_addresses(hostname: str) -> list[str]:
    try:
        records = socket.getaddrinfo(
            hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except OSError as error:
        raise RssFeedError(f"Could not resolve feed host: {error}") from error

    addresses = list(dict.fromkeys(record[4][0] for record in records))
    if not addresses:
        raise RssFeedError("Feed host did not resolve to an address")
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as error:
            raise RssFeedError("Feed host resolved to an invalid IP address") from error
        if not parsed.is_global:
            raise RssFeedError("Feed host must resolve only to public IP addresses")
    return addresses


def _validate_feed_url(url: str):
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise RssFeedError("Feed URL is invalid") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or len(url) > 2048
    ):
        raise RssFeedError("Feed URL must use HTTPS on the standard port without credentials")
    return parsed


def _canonicalize_article_url(url: str) -> str:
    parsed = _validate_feed_url(url)
    if parsed.fragment:
        raise RssFeedError("Article URLs must not contain fragments")
    hostname = parsed.hostname
    if hostname is None:
        raise RssFeedError("Article URL must include a hostname")
    if ":" in hostname:
        hostname = f"[{hostname.lower()}]"
    else:
        hostname = hostname.lower()
    if parsed.port not in (None, 443):
        hostname = f"{hostname}:{parsed.port}"
    return urlunsplit(("https", hostname, parsed.path or "/", parsed.query, ""))


def parse_rss_feed(payload: bytes) -> ParsedRssFeed:
    if len(payload) > MAX_FEED_BYTES:
        raise RssFeedError(f"Feed exceeds the {MAX_FEED_BYTES // (1024 * 1024)} MiB limit")
    declarations = payload.upper()
    if b"<!DOCTYPE" in declarations or b"<!ENTITY" in declarations:
        raise RssFeedError("Feed DTD and entity declarations are not supported")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise RssFeedError("Feed response is not valid RSS/XML") from error

    entries = [element for element in root.iter() if _local_name(element.tag) == "item"]
    if not entries:
        raise RssFeedError("Feed response contains no RSS items")

    invalid_items = max(0, len(entries) - MAX_FEED_ITEMS)
    parsed_items: list[RssItem] = []
    for entry in entries[:MAX_FEED_ITEMS]:
        title = _plain_text(_child_text(entry, "title"))[:300]
        description = _plain_text(_child_text(entry, "description"))[:MAX_DESCRIPTION_LENGTH]
        url = _child_text(entry, "link").strip()
        published = _parse_timestamp(_child_text(entry, "pubDate", "date"))
        try:
            canonical_url = _canonicalize_article_url(url)
        except RssFeedError:
            invalid_items += 1
            continue
        if not title or not published or len(url) > 2048:
            invalid_items += 1
            continue
        parsed_items.append(
            RssItem(
                title=title,
                description=description,
                url=canonical_url,
                published_at=published,
            )
        )

    return ParsedRssFeed(items=parsed_items, invalid_items=invalid_items)


def fetch_rss_feed(feed: RssFeed) -> ParsedRssFeed:
    parsed_url = _validate_feed_url(feed.url)
    hostname = parsed_url.hostname
    if hostname is None:
        raise RssFeedError("Feed URL must include a hostname")
    addresses = _resolve_public_addresses(hostname)
    path = parsed_url.path or "/"
    if parsed_url.query:
        path += f"?{parsed_url.query}"
    headers = {
        "Accept": "application/rss+xml, application/xml, text/xml",
        "User-Agent": "SIBERLENS-AI/0.1 (operator-triggered RSS importer)",
        "Host": hostname,
        "Connection": "close",
    }

    last_error: OSError | None = None
    for address in addresses:
        connection = _PinnedHTTPSConnection(hostname, address, REQUEST_TIMEOUT_SECONDS)
        try:
            connection.request("GET", path, headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise RssFeedError(
                    f"Feed server returned HTTP {response.status}; redirects are not followed"
                )
            payload = response.read(MAX_FEED_BYTES + 1)
            return parse_rss_feed(payload)
        except RssFeedError:
            raise
        except (OSError, http.client.HTTPException, ssl.SSLError) as error:
            last_error = error
        finally:
            connection.close()

    raise RssFeedError(f"Feed request failed: {last_error or 'no public address connected'}")


def persist_rss_items(
    session: Session,
    feed: RssFeed,
    parsed_feed: ParsedRssFeed,
) -> RssSyncResult:
    dataset = session.get(Dataset, feed.dataset_id) if feed.dataset_id else None
    if dataset is None:
        dataset = Dataset(
            name=feed.name,
            source_type="rss_feed",
            row_count=0,
            status="synced",
        )
        session.add(dataset)
        session.flush()
        feed.dataset_id = dataset.id

    source_id = f"rss:{feed.id}"
    existing_rows = session.execute(
        select(Post.external_id, Post.source_url).where(
            Post.dataset_id == dataset.id,
            Post.source_id == source_id,
        )
    ).all()
    existing_ids: set[str] = set()
    for external_id, source_url in existing_rows:
        if external_id:
            existing_ids.add(external_id)
        if source_url:
            try:
                canonical_url = _canonicalize_article_url(source_url)
            except RssFeedError:
                continue
            existing_ids.add(hashlib.sha256(canonical_url.encode("utf-8")).hexdigest())

    new_items: list[RssItem] = []
    duplicates_skipped = 0
    identities: dict[str, RssItem] = {}
    for item in parsed_feed.items:
        canonical_url = _canonicalize_article_url(item.url)
        external_id = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
        if external_id in existing_ids:
            duplicates_skipped += 1
            continue
        existing_ids.add(external_id)
        identities[external_id] = item

    inserted_count = 0
    if identities:
        rows = [
            {
                "dataset_id": dataset.id,
                "external_id": external_id,
                "source_url": item.url,
                "timestamp": item.published_at,
                "source_id": source_id,
                "text": item.text,
                "content_hash": hashlib.sha256(
                    _SPACE_PATTERN.sub(" ", item.text).encode("utf-8")
                ).hexdigest(),
            }
            for external_id, item in identities.items()
        ]
        if session.get_bind().dialect.name == "postgresql":
            result = session.execute(
                postgresql_insert(Post)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=[
                        Post.dataset_id,
                        func.coalesce(Post.source_id, ""),
                        Post.external_id,
                    ],
                    index_where=Post.external_id.is_not(None),
                )
            )
            inserted_count = result.rowcount or 0
            duplicates_skipped += len(rows) - inserted_count
        else:
            session.add_all(Post(**row) for row in rows)
            session.flush()
            inserted_count = len(rows)

    dataset.row_count += inserted_count
    dataset.status = "synced"
    feed.last_synced_at = datetime.now(timezone.utc)
    feed.last_sync_status = "success"
    feed.last_sync_error = None
    session.commit()

    return RssSyncResult(
        dataset_id=dataset.id,
        items_received=len(parsed_feed.items),
        items_inserted=inserted_count,
        duplicates_skipped=duplicates_skipped,
        invalid_items=parsed_feed.invalid_items,
    )
