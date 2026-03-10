"""Telegram bot Application factory — registers all handlers."""
from __future__ import annotations

import html
import traceback

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config.settings import Settings

logger = structlog.get_logger()


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler — log the error and notify the user."""
    logger.error(
        "telegram.handler_error",
        error=str(context.error),
        traceback="".join(
            traceback.format_exception(
                type(context.error), context.error, context.error.__traceback__
            )
        ),
    )
    if isinstance(update, Update) and update.effective_message:
        error_text = html.escape(str(context.error))
        await update.effective_message.reply_text(
            f"Something went wrong: {error_text}\n\n"
            "Please try again. If the problem persists, contact support."
        )


async def _post_init(application: Application) -> None:
    """Register bot commands with Telegram's native menu button."""
    await application.bot.set_my_commands([
        BotCommand("start", "Show dashboard"),
        BotCommand("subscriptions", "View your subscriptions"),
        BotCommand("help", "Command reference"),
        BotCommand("connect", "Connect email inbox"),
        BotCommand("mydata", "Export your data"),
        BotCommand("mycreds", "List stored credentials"),
        BotCommand("deleteaccount", "Delete your account"),
    ])
    logger.info("bot.commands_registered")


def create_bot_application(
    token: str,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    gmail_oauth: object | None = None,
    outlook_oauth: object | None = None,
) -> Application:
    app = Application.builder().token(token).post_init(_post_init).build()

    app.bot_data["session_factory"] = session_factory
    app.bot_data["settings"] = settings
    if gmail_oauth:
        app.bot_data["gmail_oauth"] = gmail_oauth
    if outlook_oauth:
        app.bot_data["outlook_oauth"] = outlook_oauth

    from src.telegram.handlers.add import build_add_subscription_conversation
    from src.telegram.handlers.confirm import confirm_handler
    from src.telegram.handlers.credentials import (
        build_addcreds_conversation,
        deletecreds_handler,
        mycreds_handler,
    )
    from src.telegram.handlers.dashboard import dashboard_callback_handler
    from src.telegram.handlers.deleteaccount import (
        deleteaccount_confirm_handler,
        deleteaccount_handler,
    )
    from src.telegram.handlers.fallback import fallback_handler
    from src.telegram.handlers.help import help_handler
    from src.telegram.handlers.mydata import mydata_handler
    from src.telegram.handlers.oauth_connect import connect_handler
    from src.telegram.handlers.remove import remove_handler
    from src.telegram.handlers.start import start_handler
    from src.telegram.handlers.subscriptions import subscriptions_handler

    # Global error handler — surfaces errors to the user
    app.add_error_handler(_error_handler)

    # ── Conversation handlers (must be registered first) ──
    app.add_handler(build_addcreds_conversation())
    app.add_handler(build_add_subscription_conversation())

    # ── Callback query handler for dashboard buttons ──
    # (add_subscription callbacks are handled by the ConversationHandler above)
    app.add_handler(CallbackQueryHandler(dashboard_callback_handler))

    # ── Command handlers ──
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("subscriptions", subscriptions_handler))
    app.add_handler(CommandHandler("mydata", mydata_handler))
    app.add_handler(CommandHandler("deleteaccount", deleteaccount_handler))
    app.add_handler(CommandHandler("mycreds", mycreds_handler))
    app.add_handler(CommandHandler("deletecreds", deletecreds_handler))
    app.add_handler(CommandHandler("connect", connect_handler))

    # ── Text message handlers (specific patterns) ──
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)^YES DELETE MY ACCOUNT$"),
        deleteaccount_confirm_handler,
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)^confirm\s+.+"), confirm_handler
    ))
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)^cancel\s+.+"), remove_handler
    ))

    # ── Global fallback — must be LAST ──
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, fallback_handler
    ))

    return app
