"""Load a connector from a local module; adding a source needs no registry edit."""

from importlib import import_module
from typing import cast

from offscroll.connectors._base import Connector, ConnectorError


def get_connector(source: str) -> Connector:
    if not source.isidentifier() or source.startswith("_"):
        raise ConnectorError("Unknown source.")
    try:
        module = import_module(f"offscroll.connectors.{source}")
        return cast(Connector, module.connector)
    except ModuleNotFoundError, AttributeError:
        raise ConnectorError("Unknown source.") from None
