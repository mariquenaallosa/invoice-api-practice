from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5433/invoice"
    test_database_url: str = "postgresql+psycopg://invoice:invoice@localhost:5433/invoice_test"
    # Raw JSON of the database secret, injected by the platform (the ECS agent
    # resolves it from Secrets Manager). When it is not set, `database_url` is
    # used instead, which is what local development and the tests rely on.
    database_secret: str | None = None
    app_env: str = "development"
    log_level: str = "INFO"
    # `NoDecode` stops pydantic-settings from parsing the raw value as JSON,
    # so a comma separated list (or an empty value) can be handled below.
    cors_origins: Annotated[list[str], NoDecode] = []

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        """Accept a comma separated list, an empty value or an actual list."""
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
