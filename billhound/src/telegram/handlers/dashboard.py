"""Callback query handler for inline keyboard dashboard buttons."""
from __future__ import annotations

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()

# Sub-menus
CONNECT_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("Gmail", callback_data="connect_gmail"),
        InlineKeyboardButton("Outlook", callback_data="connect_outlook"),
    ],
])

SETTINGS_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "\U0001f4ca My Data", callback_data="my_data"
        ),
        InlineKeyboardButton(
            "\U0001f511 My Credentials", callback_data="my_creds"
        ),
    ],
    [
        InlineKeyboardButton(
            "\U0001f5d1\ufe0f Delete Account", callback_data="delete_account"
        ),
    ],
])


async def dashboard_callback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Route inline-keyboard button presses to the appropriate handler."""
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id

    if data == "view_subscriptions":
        await _handle_view_subscriptions(update, context, chat_id)

    elif data == "connect_inbox":
        await context.bot.send_message(
            chat_id,
            "Which email provider would you like to connect?",
            reply_markup=CONNECT_KEYBOARD,
        )

    elif data == "connect_gmail":
        from src.telegram.handlers.oauth_connect import _connect_provider

        await _connect_provider(update, context, "gmail")

    elif data == "connect_outlook":
        from src.telegram.handlers.oauth_connect import _connect_provider

        await _connect_provider(update, context, "outlook")

    elif data == "settings_data":
        await context.bot.send_message(
            chat_id,
            "Settings & Data",
            reply_markup=SETTINGS_KEYBOARD,
        )

    elif data == "my_data":
        await _handle_my_data(update, context, chat_id)

    elif data == "my_creds":
        await _handle_my_creds(update, context, chat_id)

    elif data == "delete_account":
        await context.bot.send_message(
            chat_id,
            "WARNING: This will permanently delete your account and all data.\n\n"
            "This includes:\n"
            "- All tracked subscriptions\n"
            "- Connected email accounts\n"
            "- Cancellation history\n"
            "- All audit logs\n\n"
            "This action CANNOT be undone.\n\n"
            "To confirm, type exactly:\n"
            "YES DELETE MY ACCOUNT",
        )

    # "add_subscription" is handled by the ConversationHandler, not here


async def _handle_view_subscriptions(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Show subscriptions via callback button."""
    from collections import defaultdict
    from datetime import date
    from decimal import Decimal

    from src.db.repositories.subscription_repo import SubscriptionRepository
    from src.db.repositories.user_repo import UserRepository
    from src.telegram.formatting import (
        format_billing_cycle,
        format_currency,
        to_monthly,
    )

    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
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
        from src.telegram.handlers.subscriptions import EMPTY_STATE_KEYBOARD

        await context.bot.send_message(
            chat_id,
            "You currently have 0 active subscriptions tracked.\n\n"
            "Get started by connecting your email or adding one manually:",
            reply_markup=EMPTY_STATE_KEYBOARD,
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
                f"  {s.service_name} \u2014 "
                f"{format_currency(s.amount)}{format_billing_cycle(s.billing_cycle)}"
                f"{renewal_info}"
            )
            total_monthly += to_monthly(s.amount, s.billing_cycle)

    lines.append(f"\nTotal: ~{format_currency(total_monthly)}/month")

    if pending:
        lines.append(f"\n\nPending Confirmation ({len(pending)}):")
        for s in pending:
            lines.append(
                f"  {s.service_name} \u2014 {format_currency(s.amount)} "
                f"(confidence: {s.confidence_score:.0%})\n"
                f'  Reply "confirm {s.service_name}" to approve'
            )

    await context.bot.send_message(chat_id, "\n".join(lines))


async def _handle_my_data(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """Export user data via callback button."""
    from src.db.repositories.user_repo import UserRepository
    from src.trust.privacy_manager import PrivacyManager

    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
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
        lines.append(f"  {s['service_name']} \u2014 {s['amount']} {s['currency']}")

    lines.append(f"\nConnected emails: {len(data['connected_email_providers'])}")
    lines.append(f"Cancellation history: {len(data['cancellation_history'])}")
    lines.append(f"Audit log entries: {data['audit_log_entry_count']}")
    lines.append(f"\nExported at: {str(data['exported_at'])[:19]}")

    await context.bot.send_message(chat_id, "\n".join(lines))


async def _handle_my_creds(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int
) -> None:
    """List stored credentials via callback button."""
    from src.db.repositories.service_credential_repo import ServiceCredentialRepository
    from src.db.repositories.user_repo import UserRepository
    from src.trust.encryption import EncryptionService

    session_factory = context.bot_data["session_factory"]
    settings = context.bot_data["settings"]
    encryption = EncryptionService(settings.encryption_key.get_secret_value())

    async with session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(update.effective_user.id)
        if not user:
            await context.bot.send_message(
                chat_id, "You need to register first. Send /start"
            )
            return

        repo = ServiceCredentialRepository(session, encryption)
        credentials = await repo.get_by_user(user.id)

        if not credentials:
            await context.bot.send_message(
                chat_id,
                "No stored credentials.\n"
                "Use /addcreds <service> to add login credentials.",
            )
            return

        lines = ["Stored credentials:\n"]
        for cred in credentials:
            username = repo.decrypt_username(cred)
            lines.append(f"  {cred.service_name}: {username}")
        lines.append("\nPasswords are encrypted and never displayed.")
        lines.append("Use /deletecreds <service> to remove credentials.")

        await context.bot.send_message(chat_id, "\n".join(lines))
