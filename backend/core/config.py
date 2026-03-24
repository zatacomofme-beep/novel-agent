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
    chroma_host: str = Field(default="chroma", alias="CHROMA_HOST")
    chroma_port: int = Field(default=8001, alias="CHROMA_PORT")
    chroma_collection_prefix: str = Field(
        default="novel_story_engine",
        alias="CHROMA_COLLECTION_PREFIX",
    )
    chroma_embedding_dimensions: int = Field(
        default=256,
        alias="CHROMA_EMBEDDING_DIMENSIONS",
    )
    chroma_request_timeout_seconds: int = Field(
        default=10,
        alias="CHROMA_REQUEST_TIMEOUT_SECONDS",
    )
    story_engine_default_embedding_model: str = Field(
        default="text-embedding-3-large",
        alias="STORY_ENGINE_DEFAULT_EMBEDDING_MODEL",
    )

    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=30,
        alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    model_gateway_api_key: Optional[str] = Field(default=None, alias="MODEL_GATEWAY_API_KEY")
    model_gateway_base_url: Optional[str] = Field(
        default="https://yunwu.ai/v1",
        alias="MODEL_GATEWAY_BASE_URL",
    )
    default_model: str = Field(default="claude-3-5-sonnet", alias="DEFAULT_MODEL")
    model_request_timeout_seconds: int = Field(
        default=45,
        alias="MODEL_REQUEST_TIMEOUT_SECONDS",
    )
    model_max_retries: int = Field(default=2, alias="MODEL_MAX_RETRIES")
    story_engine_outline_model: str = Field(default="gpt-5.4", alias="STORY_ENGINE_OUTLINE_MODEL")
    story_engine_guardian_model: str = Field(default="gpt-5.4", alias="STORY_ENGINE_GUARDIAN_MODEL")
    story_engine_logic_model: str = Field(
        default="claude-opus-4-6",
        alias="STORY_ENGINE_LOGIC_MODEL",
    )
    story_engine_commercial_model: str = Field(
        default="deepseek-v3.2",
        alias="STORY_ENGINE_COMMERCIAL_MODEL",
    )
    story_engine_style_model: str = Field(
        default="gemini-3.1-pro-preview",
        alias="STORY_ENGINE_STYLE_MODEL",
    )
    story_engine_anchor_model: str = Field(default="gpt-5.4", alias="STORY_ENGINE_ANCHOR_MODEL")
    story_engine_arbitrator_model: str = Field(
        default="gpt-5.4",
        alias="STORY_ENGINE_ARBITRATOR_MODEL",
    )
    story_engine_stream_model: str = Field(default="gpt-5.4", alias="STORY_ENGINE_STREAM_MODEL")
    redis_task_events_channel_prefix: str = Field(
        default="task_updates",
        alias="REDIS_TASK_EVENTS_CHANNEL_PREFIX",
    )

    revision_min_overall_score_threshold: float = Field(
        default=0.75,
        alias="REVISION_MIN_OVERALL_SCORE_THRESHOLD",
    )
    revision_max_ai_taste_score_threshold: float = Field(
        default=0.35,
        alias="REVISION_MAX_AI_TASTE_SCORE_THRESHOLD",
    )
    approval_min_final_score_threshold: float = Field(
        default=0.70,
        alias="APPROVAL_MIN_FINAL_SCORE_THRESHOLD",
    )
    approval_max_ai_taste_score_threshold: float = Field(
        default=0.40,
        alias="APPROVAL_MAX_AI_TASTE_SCORE_THRESHOLD",
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
