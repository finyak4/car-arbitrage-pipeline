from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_path: Path
    db_out_path: Path

    discovery_pages: int = Field(default=100)
    retrieve_pages: int = Field(default=1000)
    date_for_data: str | None = None

    allowed_toyotas: list[str]

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="APP_", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
