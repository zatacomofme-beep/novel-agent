from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Long Novel Agent", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    cors_allowed_origins: Optional[str] = Field(
        default=None,
        alias="CORS_ALLOWED_ORIGINS",
        description="Comma-separated list of allowed CORS origins. Use * for all (dev only).",
    )

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
    neo4j_url: str = Field(
        alias="NEO4J_URL",
    )
    neo4j_auth: tuple[str, str] = Field(
        alias="NEO4J_AUTH",
    )
    vector_embedding_dimensions: int = Field(
        default=128,
        alias="VECTOR_EMBEDDING_DIMENSIONS",
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
    refresh_token_expire_days: int = Field(
        default=7,
        alias="REFRESH_TOKEN_EXPIRE_DAYS",
    )

    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    model_gateway_api_key: Optional[str] = Field(default=None, alias="MODEL_GATEWAY_API_KEY")
    model_gateway_base_url: Optional[str] = Field(
        default="https://yunwu.ai/v1",
        alias="MODEL_GATEWAY_BASE_URL",
    )
    model_routing_admin_emails: str = Field(
        default="",
        alias="MODEL_ROUTING_ADMIN_EMAILS",
    )
    default_model: str = Field(default="gpt-5.4", alias="DEFAULT_MODEL")
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
    story_engine_outline_max_debate_rounds: int = Field(
        default=5,
        alias="STORY_ENGINE_OUTLINE_MAX_DEBATE_ROUNDS",
    )
    story_engine_final_verify_max_rounds: int = Field(
        default=6,
        alias="STORY_ENGINE_FINAL_VERIFY_MAX_ROUNDS",
    )
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
    legacy_chapter_routes_mode: Literal["compat", "gone"] = Field(
        default="compat",
        alias="LEGACY_CHAPTER_ROUTES_MODE",
    )

    coordinator_max_revision_rounds: int = Field(
        default=3,
        alias="COORDINATOR_MAX_REVISION_ROUNDS",
        description="Maximum revision rounds in coordinator convergence loop.",
    )
    coordinator_max_debate_rounds: int = Field(
        default=3,
        alias="COORDINATOR_MAX_DEBATE_ROUNDS",
        description="Maximum debate rounds between agents.",
    )
    model_gateway_sync_timeout_seconds: int = Field(
        default=300,
        alias="MODEL_GATEWAY_SYNC_TIMEOUT_SECONDS",
        description="Timeout for synchronous model generation in thread pool.",
    )
    summary_truncate_length: int = Field(
        default=220,
        alias="SUMMARY_TRUNCATE_LENGTH",
        description="Truncation length for short summaries.",
    )
    summary_max_length: int = Field(
        default=300,
        alias="SUMMARY_MAX_LENGTH",
        description="Maximum length for long summaries.",
    )
    stream_enrichment_max_hops: int = Field(
        default=5,
        alias="STREAM_ENRICHMENT_MAX_HOPS",
        description="Max hops for causal path queries in stream enrichment.",
    )

    langsmith_enabled: bool = Field(
        default=False,
        alias="LANGSMITH_ENABLED",
    )
    langsmith_api_key: Optional[str] = Field(
        default=None,
        alias="LANGSMITH_API_KEY",
    )
    langsmith_project: str = Field(
        default="novel-agent",
        alias="LANGSMITH_PROJECT",
    )
    cache_service_enabled: bool = Field(
        default=True,
        alias="CACHE_SERVICE_ENABLED",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    @property
    def model_routing_admin_email_set(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.model_routing_admin_emails.split(",")
            if item.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
