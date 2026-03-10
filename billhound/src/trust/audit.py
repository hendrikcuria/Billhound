"""
Append-only audit log writer.
Only exposes log() — no update, no delete.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog


class AuditWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        action: str,
        *,
        user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
