"""Callback query handler for inline keyboard dashboard buttons."""
from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()


async def dashboard_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route inline-keyboard button presses to the appropriate handler."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "connect_gmail":
        from src.telegram.handlers.oauth_connect import _connect_provider

        await _connect_provider(update, context, "gmail")

    elif data == "connect_outlook":
        from src.telegram.handlers.oauth_connect import _connect_provider

        await _connect_provider(update, context, "outlook")

    elif data == "view_subscriptions":
        from src.telegram.handlers.subscriptions import subscriptions_handler

        # Create a pseudo-update that routes to the subscriptions handler
        await _run_as_message(update, context, subscriptions_handler)

    elif data == "my_data":
        from src.telegram.handlers.mydata import mydata_handler

        await _run_as_message(update, context, mydata_handler)

    else:
        await query.edit_message_text(f"Unknown action: {data}")


async def _run_as_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    handler,
) -> None:
    """Execute a handler that expects update.message by using callback_query.message."""
    # Callback queries have query.message but not update.message
    # We need to make the handler reply to the chat
    query = update.callback_query
    chat_id = query.message.chat_id

    # Import here to get session_factory
    session_factory = context.bot_data["session_factory"]

    # For subscriptions handler
    if handler.__name__ == "subscriptions_handler":
        from src.db.repositories.subscription_repo import SubscriptionRepository
        from src.telegram.formatting import (
            format_billing_cycle,
            format_currency,
            to_monthly,
        )
        from src.telegram.handlers._common import get_user_or_reply

        from collections import defaultdict
        from datetime import date
        from decimal import Decimal

        async with session_factory() as session:
            from src.db.repositories.user_repo import UserRepository

            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(update.effective_user.id)
            if not user:
                await context.bot.send_message(
                    chat_id, "You need to register first. Send /start"
                )
                return

            sub_repo = SubscriptionRepository(session)
            active_subs = list(await sub_repo.get_active_by_user(user.id))
            pending = list(await sub_repo.get_pending_by_user(user.id))

        if not active_subs and not pending:
            await context.bot.send_message(
                chat_id,
                "You currently have 0 active subscriptions tracked.\n\n"
                "Add one manually:\n"
                "  add Netflix RM54 monthly\n\n"
                "Or connect your email to auto-detect:\n"
                "  /connect gmail",
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

        await context.bot.send_message(chat_id, "\n".join(lines))

    elif handler.__name__ == "mydata_handler":
        from src.trust.privacy_manager import PrivacyManager

        async with session_factory() as session:
            from src.db.repositories.user_repo import UserRepository

            user_repo = UserRepository(session)
            user = await user_repo.get_by_telegram_id(update.effective_user.id)
            if not user:
                await context.bot.send_message(
                    chat_id, "You need to register first. Send /start"
                )
                return

            pm = PrivacyManager(session)
            data = await pm.export_my_data(user.id)
            await session.commit()

        lines = [
            "Your Billhound Data Export\n",
            f"User: {data['user']['display_name']}",
            f"Telegram ID: {data['user']['telegram_id']}",
            f"Member since: {str(data['user']['created_at'])[:10]}",
            f"\nSubscriptions: {len(data['subscriptions'])}",
        ]
        for s in data["subscriptions"]:
            lines.append(f"  {s['service_name']} — {s['amount']} {s['currency']}")

        lines.append(f"\nConnected emails: {len(data['connected_email_providers'])}")
        lines.append(f"Cancellation history: {len(data['cancellation_history'])}")
        lines.append(f"Audit log entries: {data['audit_log_entry_count']}")
        lines.append(f"\nExported at: {str(data['exported_at'])[:19]}")

        await context.bot.send_message(chat_id, "\n".join(lines))
