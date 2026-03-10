"""/deleteaccount command — two-step account deletion.

Step 1: /deleteaccount shows warning
Step 2: User types "YES DELETE MY ACCOUNT" to confirm
"""
from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.db.repositories.user_repo import UserRepository
from src.trust.privacy_manager import PrivacyManager

logger = structlog.get_logger()


async def deleteaccount_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Step 1: Show warning, require explicit confirmation."""
    await update.message.reply_text(
        "WARNING: This will permanently delete your account and all data.\n\n"
        "This includes:\n"
        "- All tracked subscriptions\n"
        "- Connected email accounts\n"
        "- Cancellation history\n"
        "- All audit logs\n\n"
        "This action CANNOT be undone.\n\n"
        "To confirm, type exactly:\n"
        "YES DELETE MY ACCOUNT"
    )


async def deleteaccount_confirm_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Step 2: Execute deletion after confirmation."""
    session_factory = context.bot_data["session_factory"]

    async with session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(update.effective_user.id)

        if not user:
            await update.message.reply_text("No account found.")
            return

        pm = PrivacyManager(session)
        result = await pm.delete_account(user.id)
        await session.commit()

    logger.info("user.deleted", telegram_id=update.effective_user.id)

    await update.message.reply_text(
        "Account deleted successfully.\n"
        f"User ID: {result['user_id']}\n"
        "All your data has been permanently removed.\n"
        "Use /start if you ever want to create a new account."
    )
