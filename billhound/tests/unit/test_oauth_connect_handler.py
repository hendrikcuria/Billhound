"""Tests for /connect OAuth handler."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.repositories.user_repo import UserRepository
from src.telegram.handlers.oauth_connect import connect_handler


def _make_context(session_factory, gmail_oauth=None, outlook_oauth=None):
    ctx = MagicMock()
    ctx.bot_data = {"session_factory": session_factory}
    if gmail_oauth:
        ctx.bot_data["gmail_oauth"] = gmail_oauth
    if outlook_oauth:
        ctx.bot_data["outlook_oauth"] = outlook_oauth
    return ctx


def _make_update(telegram_id=12345, text="", username="testuser"):
    update = MagicMock()
    update.effective_user.id = telegram_id
    update.effective_user.username = username
    update.effective_user.full_name = "Test User"
    update.effective_user.first_name = "Test"
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestConnectHandler:
    @pytest.mark.asyncio
    async def test_no_provider_shows_usage(self, session_factory) -> None:
        update = _make_update(text="/connect")
        ctx = _make_context(session_factory)

        await connect_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Usage:" in reply
        assert "gmail" in reply
        assert "outlook" in reply

    @pytest.mark.asyncio
    async def test_unknown_provider(self, session_factory) -> None:
        update = _make_update(text="/connect yahoo")
        ctx = _make_context(session_factory)

        await connect_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Unknown provider" in reply

    @pytest.mark.asyncio
    async def test_unregistered_user(self, session_factory) -> None:
        update = _make_update(telegram_id=999999, text="/connect gmail")
        gmail_mock = MagicMock()
        ctx = _make_context(session_factory, gmail_oauth=gmail_mock)

        await connect_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "/start" in reply

    @pytest.mark.asyncio
    async def test_gmail_connect_sends_url(self, session_factory) -> None:
        # Pre-create user
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=800001,
                telegram_username="tester",
                display_name="Test",
            )
            await session.commit()

        gmail_mock = MagicMock()
        gmail_mock.get_authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=xxx"
        )

        update = _make_update(telegram_id=800001, text="/connect gmail")
        ctx = _make_context(session_factory, gmail_oauth=gmail_mock)

        await connect_handler(update, ctx)

        gmail_mock.get_authorization_url.assert_called_once()
        call_kwargs = update.message.reply_text.call_args
        reply_text = call_kwargs[0][0]
        assert "Gmail" in reply_text
        assert "reply_markup" in call_kwargs[1]

    @pytest.mark.asyncio
    async def test_outlook_connect_sends_url(self, session_factory) -> None:
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=800002,
                telegram_username="tester2",
                display_name="Test2",
            )
            await session.commit()

        outlook_mock = MagicMock()
        outlook_mock.get_authorization_url.return_value = (
            "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        )

        update = _make_update(telegram_id=800002, text="/connect outlook")
        ctx = _make_context(session_factory, outlook_oauth=outlook_mock)

        await connect_handler(update, ctx)

        outlook_mock.get_authorization_url.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Outlook" in reply_text

    @pytest.mark.asyncio
    async def test_oauth_client_not_configured(self, session_factory) -> None:
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=800003,
                telegram_username="tester3",
                display_name="Test3",
            )
            await session.commit()

        update = _make_update(telegram_id=800003, text="/connect gmail")
        # No gmail_oauth in bot_data
        ctx = _make_context(session_factory)

        await connect_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "not configured" in reply
