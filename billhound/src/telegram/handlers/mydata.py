"""/mydata command — export all user data via PrivacyManager."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.telegram.handlers._common import get_user_or_reply
from src.trust.privacy_manager import PrivacyManager


async def mydata_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
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

    await update.message.reply_text("\n".join(lines))
