"""Read-only database connector — scheduled snapshot of current-state facts (FR1)."""
import os

from app.services.connectors.base import BaseConnector, RawFragment


class DatabaseConnector(BaseConnector):
    name = "db"
    label = "Operational Database (read-only)"

    @property
    def is_configured(self) -> bool:
        return bool(os.environ.get("SOURCE_DB_URL"))

    def fetch(self) -> list[RawFragment]:
        # A read-only snapshot query lands here. Connectors never write to source
        # systems (PRD: read-only connector).
        return []
