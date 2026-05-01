from app.infrastructure.config.settings import Settings


def test_project_env_overrides_global_ai_provider_settings(monkeypatch, tmp_path) -> None:
    from app.infrastructure.config import settings as settings_module

    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_BASE_URL=https://api.anthropic.com\n"
        "ANTHROPIC_API_KEY=project-anthropic-key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_module, "_BACKEND_ENV_FILE", env_file)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "global-anthropic-key")

    settings = Settings(environment="development")

    assert settings.anthropic_base_url == "https://api.anthropic.com"
    assert settings.anthropic_api_key == "project-anthropic-key"


def test_production_uses_process_ai_provider_settings(monkeypatch, tmp_path) -> None:
    from app.infrastructure.config import settings as settings_module

    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_BASE_URL=https://api.anthropic.com\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "_BACKEND_ENV_FILE", env_file)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://production.example.com/anthropic")

    settings = Settings(environment="production")

    assert settings.anthropic_base_url == "https://production.example.com/anthropic"


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
