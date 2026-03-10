from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import CancellationStatus
from src.db.models.cancellation_log import CancellationLog
from src.db.repositories.base import BaseRepository


class CancellationLogRepository(BaseRepository[CancellationLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CancellationLog)

    async def get_by_user(
        self, user_id: uuid.UUID
    ) -> Sequence[CancellationLog]:
        stmt = (
            select(CancellationLog)
            .where(CancellationLog.user_id == user_id)
            .order_by(CancellationLog.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_monthly_savings(self, user_id: uuid.UUID) -> Decimal:
        stmt = select(
            func.coalesce(func.sum(CancellationLog.confirmed_saving_amount), 0)
        ).where(
            CancellationLog.user_id == user_id,
            CancellationLog.status == CancellationStatus.SUCCESS,
            CancellationLog.confirmed_saving_amount.isnot(None),
        )
        result = await self._session.execute(stmt)
        return Decimal(str(result.scalar_one()))
