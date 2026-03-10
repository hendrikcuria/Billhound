"""Tests for Telegram bot handlers."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import BillingCycle, SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.db.repositories.user_repo import UserRepository
from src.telegram.handlers.add import (
    AWAITING_AMOUNT,
    AWAITING_CYCLE,
    AWAITING_NAME,
    add_amount,
    add_cycle,
    add_name,
    add_start,
)
from src.telegram.handlers.confirm import confirm_handler
from src.telegram.handlers.deleteaccount import (
    deleteaccount_confirm_handler,
    deleteaccount_handler,
)
from src.telegram.handlers.fallback import fallback_handler
from src.telegram.handlers.help import help_handler
from src.telegram.handlers.mydata import mydata_handler
from src.telegram.handlers.remove import remove_handler
from src.telegram.handlers.start import start_handler
from src.telegram.handlers.subscriptions import subscriptions_handler
from tests.factories import make_subscription, make_user


def _make_context(session_factory):
    ctx = MagicMock()
    ctx.bot_data = {"session_factory": session_factory}
    ctx.user_data = {}
    return ctx


def _make_update(telegram_id=12345, text="", username="testuser", first_name="Test"):
    update = MagicMock()
    update.effective_user.id = telegram_id
    update.effective_user.username = username
    update.effective_user.full_name = f"{first_name} User"
    update.effective_user.first_name = first_name
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.callback_query = None  # not a callback query
    return update


def _make_callback_update(telegram_id=12345, callback_data=""):
    update = MagicMock()
    update.effective_user.id = telegram_id
    update.effective_user.username = "testuser"
    update.effective_user.full_name = "Test User"
    update.effective_user.first_name = "Test"
    update.message = None
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.message.reply_text = AsyncMock()
    update.callback_query.message.chat_id = telegram_id
    update.effective_chat.id = telegram_id
    return update


class TestStartHandler:
    @pytest.mark.asyncio
    async def test_new_user_registered(self, session_factory) -> None:
        update = _make_update(telegram_id=900001)
        ctx = _make_context(session_factory)

        await start_handler(update, ctx)

        # User should be created
        async with session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(900001)
            assert user is not None
            assert user.telegram_username == "testuser"

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Welcome to Billhound" in reply_text
        # Should include dashboard keyboard
        reply_kwargs = update.message.reply_text.call_args[1]
        assert "reply_markup" in reply_kwargs

    @pytest.mark.asyncio
    async def test_returning_user(self, session_factory) -> None:
        # Pre-create user
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(
                telegram_id=900002,
                telegram_username="old_name",
                display_name="Old Name",
            )
            await session.commit()

        update = _make_update(telegram_id=900002, username="new_name")
        ctx = _make_context(session_factory)

        await start_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Welcome back" in reply_text
        # Should include dashboard keyboard
        reply_kwargs = update.message.reply_text.call_args[1]
        assert "reply_markup" in reply_kwargs

        # Username should be updated
        async with session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_telegram_id(900002)
            assert user.telegram_username == "new_name"


class TestSubscriptionsHandler:
    @pytest.mark.asyncio
    async def test_empty_ledger(self, session_factory) -> None:
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(telegram_id=900010, display_name="Test")
            await session.commit()

        update = _make_update(telegram_id=900010)
        ctx = _make_context(session_factory)

        await subscriptions_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "0 active subscriptions tracked" in reply_text
        # Should include inline buttons
        reply_kwargs = update.message.reply_text.call_args[1]
        assert "reply_markup" in reply_kwargs

    @pytest.mark.asyncio
    async def test_with_subscriptions(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900011)
            session.add(user)
            await session.flush()

            sub = make_subscription(
                user.id, service_name="Netflix", category="streaming"
            )
            session.add(sub)
            await session.commit()

        update = _make_update(telegram_id=900011)
        ctx = _make_context(session_factory)

        await subscriptions_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Netflix" in reply_text
        assert "STREAMING" in reply_text
        assert "RM54.00" in reply_text


class TestAddFSM:
    """Tests for the guided Add Subscription FSM."""

    @pytest.mark.asyncio
    async def test_add_start_asks_name(self, session_factory) -> None:
        update = _make_callback_update(
            telegram_id=900020, callback_data="add_subscription"
        )
        ctx = _make_context(session_factory)

        result = await add_start(update, ctx)

        assert result == AWAITING_NAME
        reply_text = update.callback_query.message.reply_text.call_args[0][0]
        assert "name of the service" in reply_text

    @pytest.mark.asyncio
    async def test_add_name_asks_amount(self, session_factory) -> None:
        update = _make_update(telegram_id=900020, text="Netflix")
        ctx = _make_context(session_factory)

        result = await add_name(update, ctx)

        assert result == AWAITING_AMOUNT
        assert ctx.user_data["add_service_name"] == "Netflix"
        reply_text = update.message.reply_text.call_args[0][0]
        assert "Netflix" in reply_text
        assert "billing cycle" in reply_text.lower() or "amount" in reply_text.lower()

    @pytest.mark.asyncio
    async def test_add_amount_asks_cycle(self, session_factory) -> None:
        update = _make_update(telegram_id=900020, text="RM54")
        ctx = _make_context(session_factory)
        ctx.user_data["add_service_name"] = "Netflix"

        result = await add_amount(update, ctx)

        assert result == AWAITING_CYCLE
        assert ctx.user_data["add_amount"] == Decimal("54")
        # Should show cycle keyboard
        reply_kwargs = update.message.reply_text.call_args[1]
        assert "reply_markup" in reply_kwargs

    @pytest.mark.asyncio
    async def test_add_invalid_amount_retries(self, session_factory) -> None:
        update = _make_update(telegram_id=900020, text="abc")
        ctx = _make_context(session_factory)
        ctx.user_data["add_service_name"] = "Netflix"

        result = await add_amount(update, ctx)

        assert result == AWAITING_AMOUNT
        reply_text = update.message.reply_text.call_args[0][0]
        assert "valid amount" in reply_text

    @pytest.mark.asyncio
    async def test_add_cycle_creates_subscription(self, session_factory) -> None:
        # Pre-create user
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(telegram_id=900020, display_name="Test")
            await session.commit()

        update = _make_callback_update(
            telegram_id=900020, callback_data="cycle_monthly"
        )
        ctx = _make_context(session_factory)
        ctx.user_data["add_service_name"] = "Netflix"
        ctx.user_data["add_amount"] = Decimal("54")

        result = await add_cycle(update, ctx)

        assert result == -1  # ConversationHandler.END
        reply_text = update.callback_query.message.reply_text.call_args[0][0]
        assert "Added Netflix" in reply_text
        assert "RM54.00" in reply_text

        # Verify in DB
        async with session_factory() as session:
            user = await UserRepository(session).get_by_telegram_id(900020)
            subs = await SubscriptionRepository(session).get_active_by_user(user.id)
            assert len(subs) == 1
            assert subs[0].is_manually_added is True

    @pytest.mark.asyncio
    async def test_add_cycle_duplicate_rejected(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900021)
            session.add(user)
            await session.flush()

            sub = make_subscription(user.id, service_name="Netflix")
            session.add(sub)
            await session.commit()

        update = _make_callback_update(
            telegram_id=900021, callback_data="cycle_monthly"
        )
        ctx = _make_context(session_factory)
        ctx.user_data["add_service_name"] = "Netflix"
        ctx.user_data["add_amount"] = Decimal("54")

        result = await add_cycle(update, ctx)

        assert result == -1
        reply_text = update.callback_query.message.reply_text.call_args[0][0]
        assert "already exists" in reply_text


class TestRemoveHandler:
    @pytest.mark.asyncio
    async def test_cancel_existing(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900030)
            session.add(user)
            await session.flush()

            sub = make_subscription(user.id, service_name="Netflix")
            session.add(sub)
            await session.commit()

        update = _make_update(telegram_id=900030, text="cancel Netflix")
        ctx = _make_context(session_factory)

        await remove_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Cancelled Netflix" in reply_text
        assert "Confirmed saving" in reply_text

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self, session_factory) -> None:
        async with session_factory() as session:
            repo = UserRepository(session)
            await repo.create(telegram_id=900031, display_name="Test")
            await session.commit()

        update = _make_update(telegram_id=900031, text="cancel Unknown")
        ctx = _make_context(session_factory)

        await remove_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "No active subscription found" in reply_text

    @pytest.mark.asyncio
    async def test_cancel_substring_match(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900032)
            session.add(user)
            await session.flush()

            sub = make_subscription(
                user.id, service_name="Adobe Creative Cloud"
            )
            session.add(sub)
            await session.commit()

        update = _make_update(telegram_id=900032, text="cancel adobe")
        ctx = _make_context(session_factory)

        await remove_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Cancelled Adobe Creative Cloud" in reply_text


class TestConfirmHandler:
    @pytest.mark.asyncio
    async def test_confirm_pending(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900040)
            session.add(user)
            await session.flush()

            sub = make_subscription(
                user.id,
                service_name="Unknown Service",
                status=SubscriptionStatus.PENDING_CONFIRMATION,
                confidence_score=Decimal("0.45"),
            )
            session.add(sub)
            await session.commit()
            sub_id = sub.id

        update = _make_update(telegram_id=900040, text="confirm Unknown Service")
        ctx = _make_context(session_factory)

        await confirm_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Confirmed Unknown Service" in reply_text

        # Verify status changed
        async with session_factory() as session:
            sub = await SubscriptionRepository(session).get_by_id(sub_id)
            assert sub.status == SubscriptionStatus.ACTIVE


class TestMydataHandler:
    @pytest.mark.asyncio
    async def test_mydata_returns_export(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900050)
            session.add(user)
            await session.flush()
            await session.commit()

        update = _make_update(telegram_id=900050)
        ctx = _make_context(session_factory)

        await mydata_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Data Export" in reply_text
        assert "Subscriptions:" in reply_text


class TestDeleteAccountHandler:
    @pytest.mark.asyncio
    async def test_warning_shown(self, session_factory) -> None:
        update = _make_update(telegram_id=900060)
        ctx = _make_context(session_factory)

        await deleteaccount_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "WARNING" in reply_text
        assert "YES DELETE MY ACCOUNT" in reply_text

    @pytest.mark.asyncio
    async def test_confirm_deletes_account(self, session_factory) -> None:
        async with session_factory() as session:
            user = make_user(telegram_id=900061)
            session.add(user)
            await session.commit()

        update = _make_update(telegram_id=900061, text="YES DELETE MY ACCOUNT")
        ctx = _make_context(session_factory)

        await deleteaccount_confirm_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Account deleted" in reply_text

        # Verify user is gone
        async with session_factory() as session:
            user = await UserRepository(session).get_by_telegram_id(900061)
            assert user is None

    @pytest.mark.asyncio
    async def test_confirm_no_user(self, session_factory) -> None:
        update = _make_update(telegram_id=999999)
        ctx = _make_context(session_factory)

        await deleteaccount_confirm_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "No account found" in reply_text


class TestHelpHandler:
    @pytest.mark.asyncio
    async def test_help_shows_commands(self) -> None:
        update = _make_update(telegram_id=900070)
        ctx = MagicMock()

        await help_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "Command Reference" in reply_text
        assert "/subscriptions" in reply_text
        assert "cancel" in reply_text
        # Should include dashboard keyboard
        reply_kwargs = update.message.reply_text.call_args[1]
        assert "reply_markup" in reply_kwargs


class TestFallbackHandler:
    @pytest.mark.asyncio
    async def test_unrecognized_text_shows_dashboard(self) -> None:
        update = _make_update(telegram_id=900080, text="blah blah")
        ctx = MagicMock()

        await fallback_handler(update, ctx)

        reply_text = update.message.reply_text.call_args[0][0]
        assert "didn't quite catch that" in reply_text
        reply_kwargs = update.message.reply_text.call_args[1]
        assert "reply_markup" in reply_kwargs
