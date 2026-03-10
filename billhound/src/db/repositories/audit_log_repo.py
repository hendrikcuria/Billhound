"""
Audit log repository. READ-ONLY: no update or delete methods exposed.
Writes go through AuditWriter in src/trust/audit.py.
"""
from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog


class AuditLogRepository:
    """Read-only repository for audit log queries."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user(
        self, user_id: uuid.UUID, *, limit: int = 100
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_action(
        self, action: str, *, limit: int = 100
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).where(AuditLog.user_id == user_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()
