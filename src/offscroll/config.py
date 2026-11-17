"""Database settings from environment variables, never from .env."""

from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, hide_input_in_errors=True)

    database_url: SecretStr = Field(repr=False)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError, ValueError:
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection URL.") from None
        if url.drivername != "postgresql+psycopg" or not all(
            (url.username, url.password, url.host, url.database)
        ):
            raise ValueError(
                "DATABASE_URL must use postgresql+psycopg and include "
                "user, password, host, and database."
            )
        # URL query values are not masked by SQLAlchemy's URL repr.
        if url.query:
            raise ValueError("DATABASE_URL query parameters are not supported.")
        return value


def load_settings() -> Settings:
    """Read settings on demand so importing the package needs no credentials."""
    return Settings()


class SourceSettings(BaseSettings):
    """Non-database source options; secrets are optional until that source is fetched."""

    model_config = SettingsConfigDict(env_file=None, hide_input_in_errors=True)

    youtube_api_key: SecretStr | None = Field(default=None, repr=False)
    youtube_channels_file: Path = Path("config/youtube_channels.yaml")
    youtube_run_limit: int = Field(default=7999, ge=1, le=7999)
    offscroll_sources: str = "hackernews,wikipedia,youtube"

    @field_validator("offscroll_sources")
    @classmethod
    def validate_sources(cls, value: str) -> str:
        sources = [s.strip() for s in value.split(",")]
        if (
            not sources
            or len(sources) != len(set(sources))
            or any(s not in {"hackernews", "wikipedia", "youtube"} for s in sources)
        ):
            raise ValueError("OFFSCROLL_SOURCES must list unique supported source names.")
        return ",".join(sources)

    @property
    def enabled_sources(self) -> list[str]:
        return self.offscroll_sources.split(",")


class SummarySettings(BaseSettings):
    """Offline Gemini only; no dotenv and no billing-management capability."""

    model_config = SettingsConfigDict(env_file=None, hide_input_in_errors=True)
    gemini_api_key: SecretStr | None = Field(default=None, repr=False)
    gemini_model: str = Field(
        default="gemini-2.5-flash-lite", pattern=r"^gemini-[0-9.]+-flash-lite$"
    )
    summary_approved_inputs: Path = Path("config/summary_public_inputs.json")
