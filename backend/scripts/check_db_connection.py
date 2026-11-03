"""Diagnose Supabase connection modes using DATABASE_URL from the environment.

Run from the backend directory:

    python -m scripts.check_db_connection

Credentials are never hardcoded. Set DATABASE_URL in the repository root .env
(see .env.example) before running.
"""
import sys
import urllib.parse

from sqlalchemy import create_engine, text

from app.core.config import get_settings


def _pooler_variants(database_url: str) -> list[tuple[str, str]]:
    """Derive the alternative Supabase pooler URLs from the configured URL."""
    parsed = urllib.parse.urlsplit(database_url)
    if not parsed.hostname or not parsed.username or not parsed.password:
        return []

    user = urllib.parse.unquote(parsed.username)
    password = urllib.parse.unquote(parsed.password)
    encoded = urllib.parse.quote(password, safe="")

    variants: list[tuple[str, str]] = []
    if parsed.hostname.endswith(".pooler.supabase.com"):
        host = parsed.hostname
        for label, port in (("Session mode", 5432), ("Transaction mode", 6543)):
            variants.append(
                (
                    f"Pooler {label} (port {port})",
                    f"postgresql+psycopg://{user}:{encoded}@{host}:{port}/{parsed.path.lstrip('/')}",
                )
            )
    return variants


def test_connection(label: str, url: str) -> bool:
    print(f"[TEST] {label}")
    try:
        engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 15},
        )
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar()
        print("  OK")
        print(f"  PostgreSQL: {str(version)[:80]}")
        return True
    except Exception as error:  # noqa: BLE001 - diagnostic script reports every failure
        print(f"  FAILED: {type(error).__name__}: {error}")
        return False
    finally:
        print()


def main() -> int:
    settings = get_settings()
    targets = [("Configured DATABASE_URL", settings.database_url)]
    targets.extend(_pooler_variants(settings.database_url))

    results = [test_connection(label, url) for label, url in targets]

    if any(results):
        print("SUCCESS: at least one connection mode worked.")
        return 0

    print("FAILED: every connection mode was rejected.")
    print()
    print("Possible causes:")
    print("  1. DATABASE_URL is wrong or the password was rotated in Supabase")
    print("  2. Your IP is blocked (check Supabase Network Restrictions)")
    print("  3. The project is paused or not fully provisioned")
    return 1


if __name__ == "__main__":
    sys.exit(main())
