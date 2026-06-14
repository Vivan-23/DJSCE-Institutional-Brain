"""Slack connector — credential-aware stub (live history pull is post-V1)."""
import os

from app.services.connectors.base import BaseConnector, RawFragment


class SlackConnector(BaseConnector):
    name = "slack"
    label = "Slack"

    @property
    def is_configured(self) -> bool:
        return bool(os.environ.get("SLACK_BOT_TOKEN"))

    def fetch(self) -> list[RawFragment]:
        # A live Events API / history pull lands here once V1 ships connectors.
        # Until then, items are ingested by pushing them to the sync endpoint.
        return []
