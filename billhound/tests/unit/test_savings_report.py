"""Tests for SavingsReportService."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import CancellationStatus
from src.services.savings_report import SavingsReportService
from tests.factories import make_cancellation_log, make_subscription, make_user


class TestSavingsReport:
    @pytest.mark.asyncio
    async def test_report_with_active_subs(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=850001)
        session.add(user)
        await session.flush()

        sub = make_subscription(user.id, service_name="Netflix", amount=Decimal("54.00"))
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        svc = SavingsReportService(session, bot)

        await svc.send_monthly_report(user.id, user.telegram_id)

        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args.kwargs["text"]
        assert "Monthly Savings Report" in msg
        assert "Active subscriptions: 1" in msg
        assert "RM54.00" in msg

    @pytest.mark.asyncio
    async def test_report_with_cancellations(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=850002)
        session.add(user)
        await session.flush()

        log = make_cancellation_log(
            user.id,
            confirmed_saving_amount=Decimal("245.00"),
        )
        session.add(log)
        await session.flush()

        bot = AsyncMock()
        svc = SavingsReportService(session, bot)

        await svc.send_monthly_report(user.id, user.telegram_id)

        msg = bot.send_message.call_args.kwargs["text"]
        assert "RM245.00" in msg

    @pytest.mark.asyncio
    async def test_report_empty_state(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=850003)
        session.add(user)
        await session.flush()

        bot = AsyncMock()
        svc = SavingsReportService(session, bot)

        await svc.send_monthly_report(user.id, user.telegram_id)

        msg = bot.send_message.call_args.kwargs["text"]
        assert "Active subscriptions: 0" in msg

    @pytest.mark.asyncio
    async def test_report_correct_chat_id(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=850004)
        session.add(user)
        await session.flush()

        bot = AsyncMock()
        svc = SavingsReportService(session, bot)

        await svc.send_monthly_report(user.id, user.telegram_id)

        bot.send_message.assert_called_once()
        assert bot.send_message.call_args.kwargs["chat_id"] == 850004
