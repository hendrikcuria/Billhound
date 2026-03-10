from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import SubscriptionStatus
from src.db.models.subscription import Subscription
from src.db.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Subscription)

    async def get_active_by_user(
        self, user_id: uuid.UUID
    ) -> Sequence[Subscription]:
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.TRIAL,
                ]),
            )
            .order_by(Subscription.next_renewal_date.asc().nullslast())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_renewals_within(
        self, user_id: uuid.UUID, days: int
    ) -> Sequence[Subscription]:
        today = date.today()
        cutoff = today + timedelta(days=days)
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.next_renewal_date.isnot(None),
                Subscription.next_renewal_date <= cutoff,
                Subscription.next_renewal_date >= today,
            )
            .order_by(Subscription.next_renewal_date.asc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_pending_by_user(
        self, user_id: uuid.UUID
    ) -> Sequence[Subscription]:
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.PENDING_CONFIRMATION,
            )
            .order_by(Subscription.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_category(
        self, user_id: uuid.UUID, category: str
    ) -> Sequence[Subscription]:
        stmt = (
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.category == category,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()
