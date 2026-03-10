"""Pending subscription confirmation handler.

User sends "confirm <service_name>" to approve a low-confidence subscription.
"""
from __future__ import annotations

import re

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.telegram.formatting import format_billing_cycle, format_currency
from src.telegram.handlers._common import find_by_name, get_user_or_reply
from src.trust.audit import AuditWriter

logger = structlog.get_logger()

CONFIRM_PATTERN = re.compile(r"^confirm\s+(.+)$", re.IGNORECASE)


async def confirm_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    text = update.message.text.strip()
    match = CONFIRM_PATTERN.match(text)
    if not match:
        return

    service_name = match.group(1).strip()
    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return

        sub_repo = SubscriptionRepository(session)
        pending = await sub_repo.get_pending_by_user(user.id)
        target = find_by_name(pending, service_name)

        if not target:
            await update.message.reply_text(
                f'No pending subscription found matching "{service_name}"'
            )
            return

        await sub_repo.update(target, status=SubscriptionStatus.ACTIVE)

        audit = AuditWriter(session)
        await audit.log(
            action="subscription_confirmed",
            user_id=user.id,
            entity_type="subscription",
            entity_id=str(target.id),
        )
        await session.commit()

    await update.message.reply_text(
        f"Confirmed {target.service_name} — "
        f"{format_currency(target.amount)}{format_billing_cycle(target.billing_cycle)}"
    )
