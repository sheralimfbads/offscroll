"""Read-only ASGI delivery; no provider calls and no credentials at import time."""

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from pydantic_settings import SettingsError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from offscroll.config import load_settings
from offscroll.db import create_db_engine
from offscroll.delivery import PACKAGE, public_lanes, render_page
from offscroll.digests import digest_identity, read_digest
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
    try:
        identity = digest_identity(engine)
        lanes = load_public(engine)
        if digest_identity(engine) != identity:
            raise HTTPException(503, "Edition is being updated; try again.")
    except DigestError:
        raise HTTPException(404, "Digest unavailable.") from None
    generated_at = str(identity["generated_at"])
    html = render_page(
        lanes,
        date=datetime.fromisoformat(generated_at).strftime("%d %B %Y"),
        generated_at=generated_at,
        asset_prefix="/static/",
    )
    return HTMLResponse(
        html, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    )


@app.get("/manifest.webmanifest")
def manifest() -> JSONResponse:
    data = json.loads((PACKAGE / "static" / "manifest.webmanifest").read_text())
    data.update({"id": "/", "start_url": "/", "scope": "/"})
    for icon in data["icons"]:
        icon["src"] = "/static/" + icon["src"]
    return JSONResponse(data, media_type="application/manifest+json")
