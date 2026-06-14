"""Connector registry — the single place the API discovers available sources."""
from typing import Optional

from app.services.connectors.base import BaseConnector
from app.services.connectors.database_connector import DatabaseConnector
from app.services.connectors.manual import ManualConnector
from app.services.connectors.slack import SlackConnector

_CONNECTORS: dict[str, BaseConnector] = {
    c.name: c
    for c in (ManualConnector(), SlackConnector(), DatabaseConnector())
}


def all_connectors() -> list[BaseConnector]:
    return list(_CONNECTORS.values())


def get_connector(name: str) -> Optional[BaseConnector]:
    return _CONNECTORS.get(name)
