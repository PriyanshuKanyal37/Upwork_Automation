from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dotenv import dotenv_values
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
_PROJECT_SCOPED_AI_ENV_KEYS = {
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "ANTHROPIC_BASE_URL": "anthropic_base_url",
    "ANTHROPIC_API_VERSION": "anthropic_api_version",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
}


class Settings(BaseSettings):
    app_name: str = "AgentLoopr Backend"
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://<neon_user>:<neon_password>@<neon_host>/<neon_db>?sslmode=require"
    )
    database_pool_recycle_seconds: int = 900
    database_command_timeout_seconds: int = 30
    auth_secret_key: str = "change-this-in-production-please-use-32-plus-characters"
    auth_algorithm: str = "HS256"
    auth_cookie_name: str = "agentloopr_session"
    auth_session_days: int = 35
    auth_cookie_secure: bool = False
    login_rate_limit_attempts: int = 8
    login_rate_limit_window_seconds: int = 900
    global_rate_limit_requests: int = 3000
    global_rate_limit_window_seconds: int = 60
    request_timeout_seconds: float = 30.0
    idempotency_ttl_seconds: int = 3600
    idempotency_max_entries: int = 10000
    firecrawl_base_url: str = "https://api.firecrawl.dev"
    firecrawl_api_key: str | None = None
    firecrawl_timeout_seconds: float = 20.0
    firecrawl_max_retries: int = 2
    firecrawl_retry_backoff_seconds: float = 1.5
    queue_driver: str = "inline"
    redis_url: str = "redis://localhost:6379/0"
    queue_max_retries: int = 3
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2
    openai_retry_backoff_seconds: float = 1.0
    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_api_version: str = "2023-06-01"
    anthropic_timeout_seconds: float = 30.0
    anthropic_max_retries: int = 2
    anthropic_retry_backoff_seconds: float = 1.0
    connector_live_health_timeout_seconds: float = 8.0
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_authorize_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/connectors/google/callback"
    google_oauth_scopes: str = (
        "https://www.googleapis.com/auth/documents "
        "https://www.googleapis.com/auth/drive.file "
        "openid email profile"
    )
    google_oauth_state_ttl_seconds: int = 600
    google_oauth_token_url: str = "https://oauth2.googleapis.com/token"
    google_docs_api_base_url: str = "https://docs.googleapis.com/v1"
    google_drive_api_base_url: str = "https://www.googleapis.com/drive/v3"
    google_drive_upload_api_base_url: str = "https://www.googleapis.com/upload/drive/v3"
    airtable_publish_enabled: bool = False
    airtable_api_base_url: str = "https://api.airtable.com/v0"
    airtable_personal_access_token: str | None = None
    ai_max_input_tokens_per_run: int = 12000
    ai_max_output_tokens_per_run: int = 6000
    ai_enable_safety_guardrails: bool = True
    ai_provider_failure_threshold: int = 5
    ai_provider_circuit_open_seconds: int = 60
    ai_enable_job_url_llm_fallback: bool = True
    ai_job_url_parser_model: str = "gpt-4o-mini"
    ai_job_url_parser_max_output_tokens: int = 200
    cors_allowed_origins: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_allowed_origins.strip():
            return []
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    model_config = SettingsConfigDict(
        env_file=_BACKEND_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    @model_validator(mode="after")
    def prefer_project_ai_settings(self) -> "Settings":
        if self.environment.strip().lower() in {"prod", "production"}:
            return self
        if not _BACKEND_ENV_FILE.exists():
            return self

        local_env = dotenv_values(_BACKEND_ENV_FILE)
        for env_key, field_name in _PROJECT_SCOPED_AI_ENV_KEYS.items():
            value = local_env.get(env_key)
            if value is not None and value.strip():
                setattr(self, field_name, value.strip())
        return self

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        normalized = value.strip()
        if normalized.startswith("postgres://"):
            normalized = normalized.replace("postgres://", "postgresql://", 1)
        if normalized.startswith("postgresql+psycopg2://"):
            normalized = normalized.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        if normalized.startswith("postgresql://"):
            normalized = normalized.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Neon URLs often use `sslmode=require`; asyncpg expects `ssl=require`.
        if normalized.startswith("postgresql+asyncpg://"):
            parsed = urlparse(normalized)
            params = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if "sslmode" in params and "ssl" not in params:
                params["ssl"] = params["sslmode"]
            params.pop("sslmode", None)
            # asyncpg does not support channel_binding as a connect() kwarg.
            params.pop("channel_binding", None)
            normalized = urlunparse(parsed._replace(query=urlencode(params)))
        return normalized

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"dev", "development"}:
                return True
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
