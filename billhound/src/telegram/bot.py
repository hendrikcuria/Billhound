"""Telegram bot Application factory — registers all handlers."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from src.config.settings import Settings


def create_bot_application(
    token: str,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    gmail_oauth: object | None = None,
    outlook_oauth: object | None = None,
) -> Application:
    app = Application.builder().token(token).build()

    app.bot_data["session_factory"] = session_factory
    app.bot_data["settings"] = settings
    if gmail_oauth:
        app.bot_data["gmail_oauth"] = gmail_oauth
    if outlook_oauth:
        app.bot_data["outlook_oauth"] = outlook_oauth

    from src.telegram.handlers.add import add_handler
    from src.telegram.handlers.confirm import confirm_handler
    from src.telegram.handlers.credentials import (
        build_addcreds_conversation,
        deletecreds_handler,
        mycreds_handler,
    )
    from src.telegram.handlers.deleteaccount import (
        deleteaccount_confirm_handler,
        deleteaccount_handler,
    )
    from src.telegram.handlers.mydata import mydata_handler
    from src.telegram.handlers.oauth_connect import connect_handler
    from src.telegram.handlers.remove import remove_handler
    from src.telegram.handlers.start import start_handler
    from src.telegram.handlers.subscriptions import subscriptions_handler

    # ConversationHandler must be registered before generic MessageHandlers
    app.add_handler(build_addcreds_conversation())

    # Command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("subscriptions", subscriptions_handler))
    app.add_handler(CommandHandler("mydata", mydata_handler))
    app.add_handler(CommandHandler("deleteaccount", deleteaccount_handler))
    app.add_handler(CommandHandler("mycreds", mycreds_handler))
    app.add_handler(CommandHandler("deletecreds", deletecreds_handler))
    app.add_handler(CommandHandler("connect", connect_handler))

    # Text message handlers (more specific first)
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
    app.add_handler(MessageHandler(
        filters.Regex(r"(?i)^add\s+.+"), add_handler
    ))

    return app
