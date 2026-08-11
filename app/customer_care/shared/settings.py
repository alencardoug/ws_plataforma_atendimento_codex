from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = "postgresql+psycopg://oncology:oncology_demo_change_me@db:5432/oncology"
    global_maturity_mode: Literal["N1", "N2"] = "N2"
    n1_assistive_search_enabled: bool = True
    operator_max_active_conversations: int = Field(default=4, ge=1, le=20)
    anonymous_token_pepper: SecretStr
    operator_auth_secret: SecretStr
    operator_auth_ttl_minutes: int = Field(default=480, ge=5, le=1440)
    openai_api_key: SecretStr | None = None
    ai_provider: Literal["openai", "deterministic-test"] = "openai"
    ai_generation_model: str = "gpt-5-mini"
    ai_embedding_model: str = "text-embedding-3-small"
    ai_embedding_dimension: int = Field(default=1536, ge=1)
    api_root_path: str = "/api/v1"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
