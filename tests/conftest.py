"""No unit test may accidentally contact an external service."""

import httpx
import psycopg
import pytest


@pytest.fixture(autouse=True)
def prevent_live_network(request, monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError(
            "Tests must use mocked HTTP; unit tests must not connect to a database"
        )

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    if request.node.get_closest_marker("integration") is None:
        monkeypatch.setattr(psycopg, "connect", blocked)
