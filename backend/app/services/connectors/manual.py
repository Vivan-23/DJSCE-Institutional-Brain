"""
Manual connector — the always-available push source.

Email/ticket/doc providers need live credentials (post-V1). The manual connector
accepts items pushed through the sync API so any source can be ingested today by
posting normalized fragments. Used as the fallback for sources without a live
integration.
"""
from app.services.connectors.base import BaseConnector, RawFragment


class ManualConnector(BaseConnector):
    name = "manual"
    label = "Manual / Pushed"

    @property
    def is_configured(self) -> bool:
        return True  # always accepts pushed items

    def fetch(self) -> list[RawFragment]:
        return []  # nothing to pull; items arrive via sync(items=...)
