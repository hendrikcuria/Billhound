"""Global fallback handler for unrecognized text and unknown commands."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.telegram.handlers.start import DASHBOARD_KEYBOARD


async def fallback_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Catch-all for any unrecognized text message or unknown command."""
    await update.message.reply_text(
        "I didn't quite catch that. Use the menu below to navigate.",
        reply_markup=DASHBOARD_KEYBOARD,
    )
