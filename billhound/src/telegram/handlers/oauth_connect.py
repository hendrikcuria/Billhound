"""
/connect command — initiate OAuth flow for email providers.

Usage:
  /connect gmail    — Connect Gmail inbox
  /connect outlook  — Connect Outlook inbox
"""
from __future__ import annotations

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.telegram.handlers._common import get_user_or_reply

logger = structlog.get_logger()

SUPPORTED_PROVIDERS = {"gmail", "outlook"}


async def connect_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /connect <provider> command."""
    parts = (update.message.text or "").strip().split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "Usage: /connect <provider>\n\n"
            "Supported providers:\n"
            "  /connect gmail\n"
            "  /connect outlook"
        )
        return

    provider = parts[1].strip().lower()

    if provider not in SUPPORTED_PROVIDERS:
        await update.message.reply_text(
            f'Unknown provider "{provider}".\n\n'
            "Supported providers:\n"
            "  /connect gmail\n"
            "  /connect outlook"
        )
        return

    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user = await get_user_or_reply(update, session)
        if not user:
            return
        user_id = str(user.id)

    # Get the appropriate OAuth client from bot_data
    oauth_key = f"{provider}_oauth"
    oauth_client = context.bot_data.get(oauth_key)

    if not oauth_client:
        logger.error("connect.oauth_client_missing", provider=provider)
        await update.message.reply_text(
            f"{provider.title()} connection is not configured. "
            "Please contact support."
        )
        return

    auth_url = oauth_client.get_authorization_url(user_id)

    provider_name = "Gmail" if provider == "gmail" else "Outlook"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"Connect {provider_name}",
            url=auth_url,
        )]
    ])

    await update.message.reply_text(
        f"Click the button below to connect your {provider_name} inbox.\n\n"
        "You'll be redirected to sign in and grant read-only access to your emails. "
        "After authorizing, I'll automatically scan the last 90 days for subscriptions.",
        reply_markup=keyboard,
    )

    logger.info(
        "connect.auth_url_sent",
        provider=provider,
        telegram_id=update.effective_user.id,
    )
