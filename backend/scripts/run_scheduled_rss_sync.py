"""Invoke the protected RSS synchronization endpoint from a Render Cron Job."""

from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REQUEST_TIMEOUT_SECONDS = 900
MAX_RESPONSE_BYTES = 1024 * 1024


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, new_url):
        return None


def main() -> int:
    endpoint = os.environ.get("RSS_SYNC_API_URL", "").strip()
    secret = os.environ.get("RSS_SYNC_SECRET", "")
    if not endpoint:
        print("RSS_SYNC_API_URL is required", file=sys.stderr)
        return 2
    if not secret:
        print("RSS_SYNC_SECRET is required", file=sys.stderr)
        return 2

    try:
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError
    except ValueError:
        print("RSS_SYNC_API_URL must be an HTTPS URL on the standard port", file=sys.stderr)
        return 2

    request = Request(
        endpoint,
        method="POST",
        headers={
            "Accept": "application/json",
            "X-RSS-Sync-Secret": secret,
            "User-Agent": "SIBERLENS-AI-Render-Cron/0.1",
        },
    )
    try:
        opener = build_opener(_NoRedirectHandler)
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                print("Scheduled RSS sync response exceeded the size limit", file=sys.stderr)
                return 1
            result = json.loads(body)
    except HTTPError as error:
        print(f"Scheduled RSS sync returned HTTP {error.code}", file=sys.stderr)
        return 1
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
        print(
            f"Scheduled RSS sync request failed ({type(error).__name__})",
            file=sys.stderr,
        )
        return 1

    if not isinstance(result, dict):
        print("Scheduled RSS sync returned an unexpected response", file=sys.stderr)
        return 1
    summary = {
        key: result.get(key)
        for key in (
            "id",
            "trigger_type",
            "status",
            "started_at",
            "completed_at",
            "total_sources",
            "successful_sources",
            "failed_sources",
            "new_articles",
            "duplicate_articles",
            "invalid_articles",
            "error_summary",
        )
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if result.get("status") in {"successful", "partial_success"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
