from enum import StrEnum
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from scaffold.db.mysql_url import ensure_mysql_utf8mb4_charset

DEFAULT_CACHE_MAX_RETRIES = 4
DEFAULT_CACHE_RETRY_BASE_DELAY_S = 0.08


class MessagingBackend(StrEnum):
    RABBITMQ = "rabbitmq"
    MEMORY = "memory"


class AIProvider(StrEnum):
    GROQ = "groq"
    MEMORY = "memory"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    database_url_sync: str | None = None

    @field_validator("database_url")
    @classmethod
    def database_url_no_line_breaks(cls, v: str) -> str:
        v = v.strip()
        if any(c in v for c in "\n\r\t\v"):
            raise ValueError(
                "database_url must be one line with no tab or line break inside the URL "
                "(often caused by Enter after the host before :24058)"
            )
        if " uv run " in v:
            raise ValueError(
                "database_url includes extra words (e.g. uv run); in Fish use two commands: "
                "set -gx DATABASE_URL 'mysql://...'; and then uv run alembic ..."
            )
        return v

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    messaging_backend: MessagingBackend = MessagingBackend.RABBITMQ
    rabbitmq_url: str | None = None
    rabbitmq_heartbeat_s: int = 30
    rabbitmq_timeout_s: float = 15.0

    cache_url: str | None = None
    cache_max_retries: int = DEFAULT_CACHE_MAX_RETRIES
    cache_retry_base_delay_s: float = DEFAULT_CACHE_RETRY_BASE_DELAY_S

    storage_endpoint_url: str = "https://t3.storageapi.dev"
    storage_region: str = "auto"
    storage_access_key_id: str | None = None
    storage_secret_access_key: str | None = None
    storage_public_base_url: str | None = None

    ai_provider: AIProvider = AIProvider.GROQ
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model_basic: str = "llama-3.1-8b-instant"
    groq_model_intermediate: str = "llama-3.1-8b-instant"
    groq_model_complex: str = "llama-3.1-8b-instant"
    groq_model_thinking: str = "llama-3.1-8b-instant"
    groq_timeout_s: float = 120.0

    def model_post_init(self, __context: object) -> None:
        if self.database_url_sync is None:
            raw = str(self.database_url)
            if raw.startswith("mysql+asyncmy://"):
                sync = "mysql+pymysql://" + raw.removeprefix("mysql+asyncmy://")
            elif raw.startswith("mysql+aiomysql://"):
                sync = "mysql+pymysql://" + raw.removeprefix("mysql+aiomysql://")
            elif raw.startswith("mysql+pymysql://"):
                sync = raw
            elif raw.startswith("mysql://"):
                sync = "mysql+pymysql://" + raw.removeprefix("mysql://")
            else:
                sync = raw
            if sync.startswith("mysql+"):
                sync = ensure_mysql_utf8mb4_charset(sync)
            object.__setattr__(self, "database_url_sync", sync)


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate({})
