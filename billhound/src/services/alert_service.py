"""Alert service — sends proactive Telegram notifications after email scans."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from src.config.settings import Settings
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.db.repositories.user_repo import UserRepository
from src.telegram.formatting import format_billing_cycle, format_currency

logger = structlog.get_logger()


class AlertService:
    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        settings: Settings,
    ) -> None:
        self._session = session
        self._bot = bot
        self._settings = settings

    async def check_and_send_for_user(self, user_id: uuid.UUID) -> int:
        """Check all alert types for a user. Returns count of alerts sent."""
        user_repo = UserRepository(self._session)
        user = await user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            return 0

        sub_repo = SubscriptionRepository(self._session)
        alerts_sent = 0
        alerts_sent += await self._check_renewals(user.telegram_id, user.id, sub_repo)
        alerts_sent += await self._check_price_changes(
            user.telegram_id, user.id, sub_repo
        )
        return alerts_sent

    async def _check_renewals(
        self,
        telegram_id: int,
        user_id: uuid.UUID,
        sub_repo: SubscriptionRepository,
    ) -> int:
        alerts_sent = 0
        max_days = max(self._settings.renewal_alert_days)
        upcoming = await sub_repo.get_renewals_within(user_id, max_days)
        today = date.today()

        for sub in upcoming:
            days_until = (sub.next_renewal_date - today).days
            if days_until not in self._settings.renewal_alert_days:
                continue

            # Skip if already alerted today
            if sub.last_renewal_alert_sent_at == today:
                continue

            redundant_note = ""
            if sub.category:
                same_cat = await sub_repo.get_by_category(user_id, sub.category)
                others = [s for s in same_cat if s.id != sub.id]
                if others:
                    other = others[0]
                    redundant_note = (
                        f"\nYou also have {other.service_name} "
                        f"({format_currency(other.amount)}"
                        f"{format_billing_cycle(other.billing_cycle)}) "
                        f"in the same category."
                    )

            day_word = "day" if days_until == 1 else "days"
            message = (
                f"Renewal Alert\n"
                f"{sub.service_name} renews in {days_until} {day_word} "
                f"— {format_currency(sub.amount)}"
                f"{format_billing_cycle(sub.billing_cycle)}"
                f"{redundant_note}\n\n"
                f'Reply "cancel {sub.service_name.lower()}" to cancel'
            )

            try:
                await self._bot.send_message(chat_id=telegram_id, text=message)
                await sub_repo.update(sub, last_renewal_alert_sent_at=today)
                alerts_sent += 1
            except Exception:
                logger.exception(
                    "alert.send_failed",
                    user_id=str(user_id),
                    alert_type="renewal",
                )

        return alerts_sent

    async def _check_price_changes(
        self,
        telegram_id: int,
        user_id: uuid.UUID,
        sub_repo: SubscriptionRepository,
    ) -> int:
        alerts_sent = 0
        subs = await sub_repo.get_active_by_user(user_id)
        now = datetime.now(timezone.utc)

        for sub in subs:
            if not sub.price_change_detected_at or not sub.last_price:
                continue
            elapsed = (now - sub.price_change_detected_at).total_seconds()
            if elapsed > 86400:
                continue

            diff = sub.amount - sub.last_price
            direction = "increased" if diff > 0 else "decreased"

            message = (
                f"Price Change Alert\n"
                f"{sub.service_name} has {direction} from "
                f"{format_currency(sub.last_price)} to "
                f"{format_currency(sub.amount)}"
                f"{format_billing_cycle(sub.billing_cycle)}\n\n"
                f'Reply "cancel {sub.service_name.lower()}" if you want to cancel'
            )

            try:
                await self._bot.send_message(chat_id=telegram_id, text=message)
                alerts_sent += 1
            except Exception:
                logger.exception(
                    "alert.send_failed",
                    user_id=str(user_id),
                    alert_type="price_change",
                )

        return alerts_sent
