"""/help command — display command reference and dashboard."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.telegram.handlers.start import DASHBOARD_KEYBOARD

HELP_TEXT = (
    "Billhound Command Reference\n\n"
    "Slash commands:\n"
    "  /start — show dashboard\n"
    "  /subscriptions — view active subscriptions\n"
    "  /connect gmail — connect Gmail for auto-detection\n"
    "  /connect outlook — connect Outlook\n"
    "  /mydata — export your stored data\n"
    "  /mycreds — list saved service credentials\n"
    "  /addcreds <service> — store login credentials\n"
    "  /deletecreds <service> — remove credentials\n"
    "  /deleteaccount — permanently delete your account\n"
    "  /help — this message\n\n"
    "Text commands:\n"
    '  add <name> <amount> [cycle]\n'
    '    Example: add Netflix RM54 monthly\n'
    '    Example: add Gym RM150 annual\n'
    '    Cycles: weekly, monthly, quarterly, annual\n\n'
    '  confirm <name>\n'
    '    Approve a pending subscription detected from email\n\n'
    '  cancel <name>\n'
    '    Mark a subscription as cancelled\n'
)


async def help_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display the full command reference with dashboard buttons."""
    await update.message.reply_text(
        HELP_TEXT,
        reply_markup=DASHBOARD_KEYBOARD,
    )
