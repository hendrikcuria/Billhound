"""/help command — display command reference and dashboard."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.telegram.handlers.start import DASHBOARD_KEYBOARD

HELP_TEXT = (
    "Billhound Command Reference\n\n"
    "Buttons (tap below):\n"
    "  View Subscriptions \u2014 see your active subs\n"
    "  Connect Inbox \u2014 auto-detect subscriptions from email\n"
    "  Add Subscription \u2014 guided manual entry\n"
    "  Settings / Data \u2014 export, credentials, account\n\n"
    "Slash commands:\n"
    "  /start \u2014 show dashboard\n"
    "  /subscriptions \u2014 view active subscriptions\n"
    "  /connect gmail \u2014 connect Gmail\n"
    "  /connect outlook \u2014 connect Outlook\n"
    "  /mydata \u2014 export your stored data\n"
    "  /help \u2014 this message\n\n"
    "Text commands:\n"
    '  confirm <name> \u2014 approve a pending subscription\n'
    '  cancel <name> \u2014 mark a subscription as cancelled'
)


async def help_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display the full command reference with dashboard buttons."""
    await update.message.reply_text(
        HELP_TEXT,
        reply_markup=DASHBOARD_KEYBOARD,
    )
