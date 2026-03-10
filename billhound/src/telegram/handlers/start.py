"""/start command — register new user or welcome returning user.

Both flows end with the persistent inline keyboard dashboard.
"""
from __future__ import annotations

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.db.repositories.user_repo import UserRepository
from src.trust.audit import AuditWriter

logger = structlog.get_logger()

DASHBOARD_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(
            "\U0001f4f1 View Subscriptions", callback_data="view_subscriptions"
        ),
    ],
    [
        InlineKeyboardButton(
            "\U0001f517 Connect Inbox", callback_data="connect_inbox"
        ),
        InlineKeyboardButton(
            "\u2795 Add Subscription", callback_data="add_subscription"
        ),
    ],
    [
        InlineKeyboardButton(
            "\u2699\ufe0f Settings / Data", callback_data="settings_data"
        ),
    ],
])

WELCOME_TEXT = (
    "Welcome to Billhound, {name}!\n\n"
    "I track your subscriptions and alert you before renewals.\n\n"
    "Use the buttons below to get started:"
)

WELCOME_BACK_TEXT = (
    "Welcome back, {name}!\n\n"
    "What would you like to do?"
)


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
                WELCOME_TEXT.format(name=tg_user.first_name),
                reply_markup=DASHBOARD_KEYBOARD,
            )
        else:
            await user_repo.update(
                user,
                telegram_username=tg_user.username,
                display_name=tg_user.full_name,
            )
            await session.commit()
            await update.message.reply_text(
                WELCOME_BACK_TEXT.format(name=tg_user.first_name),
                reply_markup=DASHBOARD_KEYBOARD,
            )
