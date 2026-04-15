from app.infrastructure.config.settings import Settings


def test_database_url_normalizes_sslmode_for_asyncpg() -> None:
    settings = Settings(
        database_url=(
            "postgresql://user:pass@host.neon.tech/dbname?sslmode=require&application_name=test-app"
        )
    )
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in settings.database_url
    assert "sslmode=" not in settings.database_url
    assert "application_name=test-app" in settings.database_url


def test_database_url_strips_channel_binding_for_asyncpg() -> None:
    settings = Settings(
        database_url=(
            "postgresql://user:pass@host.neon.tech/dbname?sslmode=require&channel_binding=require"
        )
    )
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "ssl=require" in settings.database_url
    assert "sslmode=" not in settings.database_url
    assert "channel_binding=" not in settings.database_url
