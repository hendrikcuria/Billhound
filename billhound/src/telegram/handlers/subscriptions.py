"""/subscriptions command — living subscription ledger view."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from telegram import Update
from telegram.ext import ContextTypes

from src.config.constants import SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.telegram.formatting import format_billing_cycle, format_currency, to_monthly
from src.telegram.handlers._common import get_user_or_reply


async def subscriptions_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return

        sub_repo = SubscriptionRepository(session)
        active_subs = await sub_repo.get_active_by_user(user.id)
        pending = await sub_repo.get_pending_by_user(user.id)

    if not active_subs and not pending:
        await update.message.reply_text(
            "No active subscriptions found.\n"
            'Add one with: add Netflix RM54 monthly'
        )
        return

    lines = ["Your Active Subscriptions\n"]
    total_monthly = Decimal("0")

    by_category: dict[str, list] = defaultdict(list)
    for s in active_subs:
        by_category[s.category or "other"].append(s)

    for category, items in sorted(by_category.items()):
        lines.append(f"\n{category.upper()}")
        for s in items:
            renewal_info = ""
            if s.next_renewal_date:
                days_until = (s.next_renewal_date - date.today()).days
                renewal_info = f" (renews in {days_until}d)"
            lines.append(
                f"  {s.service_name} — "
                f"{format_currency(s.amount)}{format_billing_cycle(s.billing_cycle)}"
                f"{renewal_info}"
            )
            total_monthly += to_monthly(s.amount, s.billing_cycle)

    lines.append(f"\nTotal: ~{format_currency(total_monthly)}/month")

    if pending:
        lines.append(f"\n\nPending Confirmation ({len(pending)}):")
        for s in pending:
            lines.append(
                f"  {s.service_name} — {format_currency(s.amount)} "
                f"(confidence: {s.confidence_score:.0%})\n"
                f'  Reply "confirm {s.service_name}" to approve'
            )

    await update.message.reply_text("\n".join(lines))
