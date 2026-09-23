from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareCloud Patient Registration"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/patients.db"
    public_base_url: str = "http://localhost:8000"
    vapi_private_api_key: str | None = None
    vapi_webhook_secret: str | None = None
    vapi_assistant_id: str | None = None
    vapi_phone_number: str | None = None
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()

