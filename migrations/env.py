"""Run migrations using environment settings, without printing connection details."""

from alembic import context
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import load_settings
from offscroll.db import create_db_engine


def run_migrations() -> None:
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_db_engine(load_settings())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


try:
    run_migrations()
except (ValidationError, SettingsError):
    raise SystemExit("Invalid database configuration. Check the exported DATABASE_URL.") from None
except SQLAlchemyError:
    # Driver exceptions may contain credentials; never echo the original error.
    raise SystemExit(
        "Database migration failed. Check database availability, credentials, and schema state."
    ) from None
