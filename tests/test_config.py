import logging
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pydantic_settings.sources import DotEnvSettingsSource

from offscroll.config import load_settings


def test_settings_read_environment_and_mask_secrets(monkeypatch, caplog):
    password = uuid4().hex
    url = f"postgresql+psycopg://test_user:{password}@127.0.0.1/test_database"
    monkeypatch.setenv("DATABASE_URL", url)

    settings = load_settings()

    assert settings.database_url.get_secret_value() == url
    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("Settings: %s %r", settings, settings)
    for output in (
        str(settings),
        repr(settings),
        str(settings.database_url),
        repr(settings.database_url),
        settings.model_dump_json(),
        caplog.text,
    ):
        assert password not in output
        assert url not in output


def test_missing_environment_does_not_read_dotenv(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    dotenv_reader = Mock(side_effect=AssertionError("Settings must not read .env"))
    monkeypatch.setattr(DotEnvSettingsSource, "_read_env_file", dotenv_reader)
    with pytest.raises(ValidationError, match="database_url"):
        load_settings()
    dotenv_reader.assert_not_called()


@pytest.mark.parametrize(
    "template",
    [
        "invalid-{value}",
        "postgresql+psycopg://user:{value}@localhost:invalid_port/database",
        "postgresql://user:{value}@localhost/database",
        "postgresql+psycopg://user:{value}@localhost",
        "postgresql+psycopg://user:{value}@localhost/database?password={value}",
    ],
)
def test_invalid_configuration_hides_input(monkeypatch, template):
    value = uuid4().hex
    url = template.format(value=value)
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(ValidationError) as exc:
        load_settings()
    assert "DATABASE_URL" in str(exc.value)
    assert value not in str(exc.value)
    assert value not in repr(exc.value)
