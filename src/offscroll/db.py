"""SQLAlchemy engine and session factories; no connections at import time."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from offscroll.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    """Create an engine; SQLAlchemy opens connections only when requested."""
    return create_engine(
        settings.database_url.get_secret_value(),
        echo=False,
        echo_pool=False,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create sessions bound to an engine; callers manage transaction scope."""
    return sessionmaker(bind=engine)
