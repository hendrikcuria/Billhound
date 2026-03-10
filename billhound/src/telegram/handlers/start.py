"""/start command — register new user or welcome returning user."""
from __future__ import annotations

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from src.db.repositories.user_repo import UserRepository
from src.trust.audit import AuditWriter

logger = structlog.get_logger()


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_factory = context.bot_data["session_factory"]
    tg_user = update.effective_user

    async with session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_telegram_id(tg_user.id)

        if user is None:
            user = await user_repo.create(
                telegram_id=tg_user.id,
                telegram_username=tg_user.username,
                display_name=tg_user.full_name,
            )
            audit = AuditWriter(session)
            await audit.log(action="user_registered", user_id=user.id)
            await session.commit()
            logger.info("user.registered", telegram_id=tg_user.id)
            await update.message.reply_text(
                f"Welcome to Billhound, {tg_user.first_name}!\n\n"
                "I track your subscriptions and alert you before renewals.\n\n"
                "Commands:\n"
                "/subscriptions — view your active subscriptions\n"
                '"add Netflix RM54 monthly" — add a subscription\n'
                '"cancel Netflix" — initiate cancellation\n'
                "/mydata — export your data\n"
                "/deleteaccount — delete your account"
            )
        else:
            await user_repo.update(
                user,
                telegram_username=tg_user.username,
                display_name=tg_user.full_name,
            )
            await session.commit()
            await update.message.reply_text(f"Welcome back, {tg_user.first_name}!")
