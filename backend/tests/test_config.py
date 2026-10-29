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
