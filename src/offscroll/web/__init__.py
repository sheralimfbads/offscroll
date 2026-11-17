"""Read-only ASGI delivery; no provider calls and no credentials at import time."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import load_settings
from offscroll.db import create_db_engine
from offscroll.delivery import PACKAGE, public_lanes, render_page
from offscroll.digests import read_digest
from offscroll.ranking import DigestError

app = FastAPI(title="Offscroll", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=PACKAGE / "static"), name="static")


def database() -> Iterator[Engine]:
    engine = None
    try:
        engine = create_db_engine(load_settings())
        yield engine
    except SQLAlchemyError, ValidationError, SettingsError:
        raise HTTPException(503, "Database unavailable.") from None
    finally:
        if engine is not None:
            engine.dispose()


def load_public(engine: Engine, week: str | None = None) -> dict[str, list[dict[str, object]]]:
    try:
        return public_lanes(read_digest(engine, week=week, purge=False))
    except DigestError:
        raise HTTPException(404, "Digest unavailable or invalid ISO week.") from None


@app.get("/healthz")
def health(engine: Annotated[Engine, Depends(database)]) -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/digests/latest")
def latest(engine: Annotated[Engine, Depends(database)]) -> dict[str, list[dict[str, object]]]:
    return load_public(engine)


@app.get("/api/digests/{iso_week}")
def by_week(
    iso_week: str, engine: Annotated[Engine, Depends(database)]
) -> dict[str, list[dict[str, object]]]:
    return load_public(engine, iso_week)


@app.get("/", response_class=HTMLResponse)
def index(engine: Annotated[Engine, Depends(database)]) -> HTMLResponse:
    html = render_page(
        load_public(engine), date=datetime.now(UTC).strftime("%d %B %Y"), asset_prefix="/static/"
    )
    return HTMLResponse(
        html, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    )
