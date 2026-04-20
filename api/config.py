"""Runtime configuration loaded from environment/.env.

`make install` generates .env with a fresh API_KEY. Nothing here touches the
filesystem — callers access `settings` and resolve paths through pathlib.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = Field(default="dev-local-key-not-for-prod")
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    data_dir: Path = ROOT / "data"
    notes_dir: Path = ROOT / "notes"
    db_path: Path = ROOT / "data" / "cache.db"
    log_dir: Path = ROOT / "logs"

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
