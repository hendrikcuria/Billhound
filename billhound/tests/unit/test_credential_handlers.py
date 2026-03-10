"""Tests for Telegram credential management handlers."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.service_credential_repo import ServiceCredentialRepository
from src.db.repositories.user_repo import UserRepository
from src.telegram.handlers.credentials import (
    addcreds_password,
    addcreds_start,
    addcreds_username,
    deletecreds_handler,
    mycreds_handler,
)
from src.trust.encryption import EncryptionService

TEST_KEY = "a" * 64


def _make_settings():
    settings = MagicMock()
    settings.encryption_key = MagicMock()
    settings.encryption_key.get_secret_value.return_value = TEST_KEY
    return settings


def _make_context(session_factory, settings=None):
    ctx = MagicMock()
    ctx.bot_data = {
        "session_factory": session_factory,
        "settings": settings or _make_settings(),
    }
    ctx.user_data = {}
    return ctx


def _make_update(telegram_id=12345, text="", username="testuser"):
    update = MagicMock()
    update.effective_user.id = telegram_id
    update.effective_user.username = username
    update.effective_user.full_name = "Test User"
    update.effective_user.first_name = "Test"
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.delete = AsyncMock()
    update.effective_chat.send_message = AsyncMock()
    return update


class TestAddCredsStart:
    @pytest.mark.asyncio
    async def test_no_service_shows_usage(self, session_factory) -> None:
        update = _make_update(text="/addcreds")
        ctx = _make_context(session_factory)

        from telegram.ext import ConversationHandler
        result = await addcreds_start(update, ctx)

        assert result == ConversationHandler.END
        reply = update.message.reply_text.call_args[0][0]
        assert "Usage: /addcreds" in reply

    @pytest.mark.asyncio
    async def test_valid_service_asks_for_username(self, session_factory) -> None:
        update = _make_update(text="/addcreds netflix")
        ctx = _make_context(session_factory)

        result = await addcreds_start(update, ctx)

        assert result == 0  # AWAITING_USERNAME
        assert ctx.user_data["cred_service"] == "netflix"
        reply = update.message.reply_text.call_args[0][0]
        assert "username" in reply.lower()


class TestAddCredsFullFlow:
    @pytest.mark.asyncio
    async def test_full_flow_stores_credential(self, session_factory) -> None:
        """Simulate the full /addcreds conversation flow."""
        # Pre-create user
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960001,
                telegram_username="credtest",
                display_name="Cred Test",
            )
            await session.commit()

        ctx = _make_context(session_factory)

        # Step 1: /addcreds netflix
        update1 = _make_update(telegram_id=960001, text="/addcreds netflix")
        await addcreds_start(update1, ctx)
        assert ctx.user_data["cred_service"] == "netflix"

        # Step 2: Send username
        update2 = _make_update(telegram_id=960001, text="user@netflix.com")
        await addcreds_username(update2, ctx)
        assert ctx.user_data["cred_username"] == "user@netflix.com"

        # Step 3: Send password
        update3 = _make_update(telegram_id=960001, text="mypassword123")
        await addcreds_password(update3, ctx)

        # Verify password message was deleted
        update3.message.delete.assert_called_once()

        # Verify credential stored in DB
        encryption = EncryptionService(TEST_KEY)
        async with session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(960001)
            cred_repo = ServiceCredentialRepository(session, encryption)
            cred = await cred_repo.get_by_service(user.id, "netflix")
            assert cred is not None
            assert cred_repo.decrypt_username(cred) == "user@netflix.com"
            assert cred_repo.decrypt_password(cred) == "mypassword123"

        # Verify confirmation message
        reply = update3.effective_chat.send_message.call_args[0][0]
        assert "stored securely" in reply

    @pytest.mark.asyncio
    async def test_password_message_deleted(self, session_factory) -> None:
        """Password message must be deleted from chat."""
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960002,
                telegram_username="deltest",
                display_name="Del Test",
            )
            await session.commit()

        ctx = _make_context(session_factory)
        ctx.user_data["cred_service"] = "spotify"
        ctx.user_data["cred_username"] = "user@spotify.com"

        update = _make_update(telegram_id=960002, text="secretpassword")
        await addcreds_password(update, ctx)

        update.message.delete.assert_called_once()


class TestMyCredsHandler:
    @pytest.mark.asyncio
    async def test_empty_credentials(self, session_factory) -> None:
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960010,
                telegram_username="empty",
                display_name="Empty User",
            )
            await session.commit()

        update = _make_update(telegram_id=960010, text="/mycreds")
        ctx = _make_context(session_factory)

        await mycreds_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "No stored credentials" in reply

    @pytest.mark.asyncio
    async def test_shows_usernames_not_passwords(self, session_factory) -> None:
        encryption = EncryptionService(TEST_KEY)

        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960011,
                telegram_username="creds",
                display_name="Creds User",
            )
            await session.commit()

            user = await repo.get_by_telegram_id(960011)
            cred_repo = ServiceCredentialRepository(session, encryption)
            await cred_repo.store_credential(
                user_id=user.id,
                service_name="netflix",
                username="viewer@example.com",
                password="supersecret",
            )
            await session.commit()

        update = _make_update(telegram_id=960011, text="/mycreds")
        ctx = _make_context(session_factory)

        await mycreds_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "viewer@example.com" in reply
        assert "supersecret" not in reply
        assert "never displayed" in reply.lower()


class TestDeleteCredsHandler:
    @pytest.mark.asyncio
    async def test_delete_existing(self, session_factory) -> None:
        encryption = EncryptionService(TEST_KEY)

        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960020,
                telegram_username="delcreds",
                display_name="Del Creds",
            )
            await session.commit()

            user = await repo.get_by_telegram_id(960020)
            cred_repo = ServiceCredentialRepository(session, encryption)
            await cred_repo.store_credential(
                user_id=user.id,
                service_name="netflix",
                username="u@u.com",
                password="p",
            )
            await session.commit()

        update = _make_update(telegram_id=960020, text="/deletecreds netflix")
        ctx = _make_context(session_factory)

        await deletecreds_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "deleted" in reply.lower()

        # Verify actually deleted
        async with session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(960020)
            cred_repo = ServiceCredentialRepository(session, encryption)
            assert await cred_repo.get_by_service(user.id, "netflix") is None

    @pytest.mark.asyncio
    async def test_delete_not_found(self, session_factory) -> None:
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960021,
                telegram_username="notfound",
                display_name="Not Found",
            )
            await session.commit()

        update = _make_update(telegram_id=960021, text="/deletecreds spotify")
        ctx = _make_context(session_factory)

        await deletecreds_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "No credentials found" in reply

    @pytest.mark.asyncio
    async def test_no_service_shows_usage(self, session_factory) -> None:
        update = _make_update(text="/deletecreds")
        ctx = _make_context(session_factory)

        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=960022,
                telegram_username="usage",
                display_name="Usage",
            )
            await session.commit()

        update = _make_update(telegram_id=960022, text="/deletecreds")
        ctx = _make_context(session_factory)

        await deletecreds_handler(update, ctx)

        reply = update.message.reply_text.call_args[0][0]
        assert "Usage: /deletecreds" in reply
