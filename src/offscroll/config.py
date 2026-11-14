"""Database settings from environment variables, never from .env."""

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
        except (ArgumentError, ValueError):
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
