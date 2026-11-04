import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_url_can_be_configured() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://tester:secret@db.example:5432/app",
    )

    assert settings.database_url == "postgresql+psycopg://tester:secret@db.example:5432/app"


def test_database_url_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+psycopg://tester:secret@db.example:5432/app"
    monkeypatch.setenv("DATABASE_URL", database_url)

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url


def test_database_url_uses_psycopg_for_standard_postgresql_url() -> None:
    settings = Settings(_env_file=None, database_url="postgresql://db.example/siberlens")

    assert settings.database_url == "postgresql+psycopg://db.example/siberlens"


def test_database_url_rejects_non_postgresql_scheme() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL must use PostgreSQL"):
        Settings(_env_file=None, database_url="sqlite:///local.db")


def test_supabase_url_requires_https_on_standard_port() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://db.example/siberlens",
        supabase_url="https://project.supabase.co/",
    )
    assert settings.supabase_url == "https://project.supabase.co"

    for url in ("http://project.supabase.co", "https://user:pass@project.supabase.co"):
        with pytest.raises(ValidationError, match="SUPABASE_URL must be an HTTPS origin"):
            Settings(
                _env_file=None,
                database_url="postgresql+psycopg://db.example/siberlens",
                supabase_url=url,
            )


def test_scheduled_rss_requires_a_long_secret() -> None:
    database_url = "postgresql+psycopg://db.example/siberlens"
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            _env_file=None,
            database_url=database_url,
            rss_sync_secret="too-short",
        )
    with pytest.raises(ValidationError, match="RSS_SYNC_SECRET is required"):
        Settings(
            _env_file=None,
            database_url=database_url,
            rss_sync_schedule_enabled=True,
        )
    settings = Settings(
        _env_file=None,
        database_url=database_url,
        rss_sync_schedule_enabled=True,
        rss_sync_secret="a-random-secret-with-more-than-thirty-two-characters",
    )
    assert settings.rss_sync_schedule_enabled is True


def test_cors_origins_parse_comma_separated_values() -> None:
    settings = Settings(_env_file=None, cors_origins="https://app.example, http://localhost:5173")

    assert settings.cors_origins == ["https://app.example", "http://localhost:5173"]


def test_cors_origins_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example,http://localhost:5173")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["https://app.example", "http://localhost:5173"]


def test_cors_origins_reject_wildcard() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS origins are not allowed"):
        Settings(_env_file=None, cors_origins=["*"])


def test_cors_origins_reject_paths_and_embedded_wildcards() -> None:
    for origin in ("https://app.example/path", "https://*.example"):
        with pytest.raises(ValidationError, match="Invalid exact CORS origin"):
            Settings(_env_file=None, cors_origins=[origin])


def test_cors_preflight_allows_analyst_note_methods() -> None:
    from app.main import app

    cors = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    allowed = cors.kwargs["allow_methods"]

    assert "GET" in allowed
    assert "POST" in allowed
    assert "DELETE" in allowed
