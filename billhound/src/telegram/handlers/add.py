"""Manual subscription add via single text message.

Format: add <service_name> [RM]<amount> [cycle]
Examples:
    add Netflix RM54 monthly
    add Gym RM150 annual
    add Spotify 15.90
"""
from __future__ import annotations

import re
from decimal import Decimal

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import BillingCycle, SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.services.merchant_db import lookup_category
from src.telegram.formatting import format_billing_cycle, format_currency
from src.telegram.handlers._common import get_user_or_reply
from src.trust.audit import AuditWriter

logger = structlog.get_logger()

ADD_PATTERN = re.compile(
    r"^add\s+(.+?)\s+(?:RM)?(\d+(?:\.\d{1,2})?)\s*(weekly|monthly|quarterly|annual)?$",
    re.IGNORECASE,
)

_CYCLE_MAP = {
    "weekly": BillingCycle.WEEKLY,
    "monthly": BillingCycle.MONTHLY,
    "quarterly": BillingCycle.QUARTERLY,
    "annual": BillingCycle.ANNUAL,
}


async def add_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    match = ADD_PATTERN.match(text)

    if not match:
        await update.message.reply_text(
            "Format: add <name> <amount> [monthly|weekly|quarterly|annual]\n"
            "Example: add Netflix RM54 monthly"
        )
        return

    service_name = match.group(1).strip()
    amount = Decimal(match.group(2))
    cycle_str = (match.group(3) or "monthly").lower()
    billing_cycle = _CYCLE_MAP.get(cycle_str, BillingCycle.MONTHLY)

    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return

        sub_repo = SubscriptionRepository(session)
        existing = await sub_repo.get_active_by_user(user.id)
        normalized = service_name.lower().strip()

        for s in existing:
            if s.service_name.lower().strip() == normalized:
                await update.message.reply_text(
                    f"{service_name} already exists at "
                    f"{format_currency(s.amount)}{format_billing_cycle(s.billing_cycle)}"
                )
                return

        category = lookup_category(service_name)
        sub = await sub_repo.create(
            user_id=user.id,
            service_name=service_name,
            category=category,
            amount=amount,
            currency="MYR",
            billing_cycle=billing_cycle,
            status=SubscriptionStatus.ACTIVE,
            confidence_score=Decimal("1.00"),
            is_manually_added=True,
        )

        audit = AuditWriter(session)
        await audit.log(
            action="subscription_added_manually",
            user_id=user.id,
            entity_type="subscription",
            entity_id=str(sub.id),
            details={"service": service_name, "amount": str(amount)},
        )
        await session.commit()

    await update.message.reply_text(
        f"Added {service_name} — "
        f"{format_currency(amount)}{format_billing_cycle(billing_cycle)}"
    )
