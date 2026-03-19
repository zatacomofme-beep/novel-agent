from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Long Novel Agent", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    celery_broker_url: str = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(alias="CELERY_RESULT_BACKEND")
    qdrant_url: str = Field(alias="QDRANT_URL")
    qdrant_collection_prefix: str = Field(
        default="story_bible",
        alias="QDRANT_COLLECTION_PREFIX",
    )
    qdrant_request_timeout_seconds: int = Field(
        default=5,
        alias="QDRANT_REQUEST_TIMEOUT_SECONDS",
    )
    vector_embedding_dimensions: int = Field(
        default=128,
        alias="VECTOR_EMBEDDING_DIMENSIONS",
    )

    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    default_model: str = Field(default="claude-3-5-sonnet", alias="DEFAULT_MODEL")
    model_request_timeout_seconds: int = Field(
        default=45,
        alias="MODEL_REQUEST_TIMEOUT_SECONDS",
    )
    model_max_retries: int = Field(default=2, alias="MODEL_MAX_RETRIES")
    redis_task_events_channel_prefix: str = Field(
        default="task_updates",
        alias="REDIS_TASK_EVENTS_CHANNEL_PREFIX",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
