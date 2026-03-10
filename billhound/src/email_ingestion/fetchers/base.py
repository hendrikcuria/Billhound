"""Protocol for email fetchers — used for type hints and testing."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.email_ingestion.types import RawEmail


class EmailFetcher(Protocol):
    async def fetch_emails(
        self,
        *,
        since: datetime | None = None,
        max_results: int = 50,
    ) -> list[RawEmail]: ...
