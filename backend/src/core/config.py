"""Application configuration management."""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Environment
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://stepguide:stepguide_dev_password@localhost:5432/stepguide",
        description="Database connection URL"
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )

    # Security
    secret_key: str = Field(
        default="dev_secret_key_change_in_production",
        description="Secret key for JWT tokens"
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiration time in minutes"
    )

    # LLM APIs
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    anthropic_api_key: Optional[str] = Field(
        default=None,
        description="Anthropic API key"
    )

    # LM Studio (Local LLM)
    lm_studio_base_url: str = Field(
        default="http://localhost:1234/v1",
        description="LM Studio base URL for local LLM API"
    )
    lm_studio_model: str = Field(
        default="local-model",
        description="LM Studio model identifier"
    )
    enable_lm_studio: bool = Field(
        default=True,
        description="Enable LM Studio local LLM support"
    )

    # Rate limiting
    rate_limit_requests_per_minute: int = Field(
        default=60,
        description="Rate limit for API requests per minute"
    )
    guide_generation_rate_limit: int = Field(
        default=10,
        description="Rate limit for guide generation per minute"
    )

    # Performance
    max_guide_steps: int = Field(
        default=20,
        description="Maximum number of steps in a guide"
    )
    guide_generation_timeout_seconds: int = Field(
        default=30,
        description="Timeout for guide generation"
    )

    # Features
    enable_desktop_monitoring: bool = Field(
        default=False,
        description="Enable desktop monitoring features"
    )
    enable_websockets: bool = Field(
        default=True,
        description="Enable WebSocket connections"
    )

    @field_validator("database_url")
    def validate_database_url(cls, v):
        """Ensure database URL is properly formatted."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v

    @field_validator("redis_url")
    def validate_redis_url(cls, v):
        """Ensure Redis URL is properly formatted."""
        if not v.startswith("redis://"):
            raise ValueError("Redis URL must start with redis://")
        return v

    @field_validator("secret_key")
    def validate_secret_key(cls, v):
        """Ensure secret key is sufficiently complex in production."""
        if len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v

    @field_validator("log_level")
    def validate_log_level(cls, v):
        """Ensure log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("lm_studio_base_url")
    def validate_lm_studio_url(cls, v):
        """Ensure LM Studio URL is properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("LM Studio base URL must start with http:// or https://")
        if not v.endswith("/v1"):
            v = v.rstrip("/") + "/v1"
        return v

    model_config = ConfigDict(
        env_file = ".env",
        env_file_encoding = "utf-8",
        case_sensitive = False
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
