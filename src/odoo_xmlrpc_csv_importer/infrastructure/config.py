from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    url: HttpUrl = Field(...)
    db: str = Field(...)
    username: str = Field(...)
    password: SecretStr = Field(...)
    dql_file: str = "failed_records.csv"

    model_config = SettingsConfigDict(
        env_prefix="odoo_", env_file=".env", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
