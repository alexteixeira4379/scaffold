from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    )

    database_url: str
    database_url_sync: str | None = None

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    messaging_backend: MessagingBackend = MessagingBackend.RABBITMQ
    rabbitmq_url: str | None = None

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
            object.__setattr__(self, "database_url_sync", sync)


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate({})
