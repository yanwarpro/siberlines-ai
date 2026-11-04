import io
import json

from scripts import run_scheduled_rss_sync


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = io.BytesIO(payload)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.payload.close()

    def read(self, size: int = -1) -> bytes:
        return self.payload.read(size)


def test_cron_runner_posts_secret_and_prints_summary_without_secret(
    monkeypatch,
    capsys,
) -> None:
    secret = "cron-secret-that-must-not-be-printed"
    monkeypatch.setenv(
        "RSS_SYNC_API_URL",
        "https://api.example.test/api/v1/rss-sync/scheduled",
    )
    monkeypatch.setenv("RSS_SYNC_SECRET", secret)
    captured: dict[str, object] = {}

    class _Opener:
        def open(self, request, timeout):
            captured["method"] = request.method
            captured["secret"] = request.get_header("X-rss-sync-secret")
            captured["timeout"] = timeout
            return _Response(
                json.dumps(
                    {
                        "status": "partial_success",
                        "trigger_type": "scheduled",
                        "new_articles": 3,
                        "duplicate_articles": 1,
                        "secret": "must not be printed",
                    }
                ).encode()
            )

    monkeypatch.setattr(
        run_scheduled_rss_sync,
        "build_opener",
        lambda *_handlers: _Opener(),
    )

    assert run_scheduled_rss_sync.main() == 0
    assert captured == {
        "method": "POST",
        "secret": secret,
        "timeout": 900,
    }
    output = capsys.readouterr().out
    assert '"new_articles": 3' in output
    assert secret not in output
    assert "must not be printed" not in output


def test_cron_runner_rejects_non_https_endpoint(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RSS_SYNC_API_URL", "http://api.example.test/api/v1/rss-sync/scheduled")
    monkeypatch.setenv("RSS_SYNC_SECRET", "cron-secret-that-must-not-be-printed")

    assert run_scheduled_rss_sync.main() == 2
    assert "HTTPS" in capsys.readouterr().err


def test_cron_runner_requires_endpoint_and_secret(monkeypatch, capsys) -> None:
    monkeypatch.delenv("RSS_SYNC_API_URL", raising=False)
    monkeypatch.delenv("RSS_SYNC_SECRET", raising=False)

    assert run_scheduled_rss_sync.main() == 2
    assert "RSS_SYNC_API_URL is required" in capsys.readouterr().err
