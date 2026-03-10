"""Monthly savings report generator."""
from __future__ import annotations

import uuid
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from src.db.repositories.cancellation_log_repo import CancellationLogRepository
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.telegram.formatting import format_currency, to_monthly

logger = structlog.get_logger()


class SavingsReportService:
    def __init__(self, session: AsyncSession, bot: Bot) -> None:
        self._session = session
        self._bot = bot

    async def send_monthly_report(
        self, user_id: uuid.UUID, telegram_id: int
    ) -> None:
        sub_repo = SubscriptionRepository(self._session)
        cancel_repo = CancellationLogRepository(self._session)

        active_subs = await sub_repo.get_active_by_user(user_id)
        total_monthly = sum(
            (to_monthly(s.amount, s.billing_cycle) for s in active_subs),
            Decimal("0"),
        )
        total_annual = total_monthly * 12

        monthly_savings = await cancel_repo.get_monthly_savings(user_id)

        message = (
            "Monthly Savings Report\n\n"
            f"Active subscriptions: {len(active_subs)}\n"
            f"Monthly spend: {format_currency(total_monthly)}\n"
            f"Annual spend: {format_currency(total_annual)}\n\n"
            f"Total confirmed savings: {format_currency(monthly_savings)}/month\n\n"
            "Reply /subscriptions for full breakdown"
        )

        try:
            await self._bot.send_message(chat_id=telegram_id, text=message)
            logger.info("savings_report.sent", user_id=str(user_id))
        except Exception:
            logger.exception("savings_report.send_failed", user_id=str(user_id))
