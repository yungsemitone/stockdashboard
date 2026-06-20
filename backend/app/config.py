from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment / a local .env file."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        extra="ignore",
    )

    anthropic_api_key: str | None = None
    narrative_model: str = "claude-sonnet-4-6"
    fred_api_key: str | None = None
    finnhub_api_key: str | None = None
    twelve_data_api_key: str | None = None
    cors_origins: str = "http://localhost:3000"
    # Where persistent files (watchlists) live. Point this at a mounted disk in
    # production; defaults to backend/data/ for local dev.
    data_dir: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
