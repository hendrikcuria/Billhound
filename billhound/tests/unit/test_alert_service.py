"""Tests for AlertService — renewal alerts, price hike alerts, dedup."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.alert_service import AlertService
from tests.factories import make_subscription, make_user


def _make_settings(**overrides):
    settings = MagicMock()
    settings.renewal_alert_days = overrides.get("renewal_alert_days", [7, 3, 1])
    return settings


class TestAlertService:
    @pytest.mark.asyncio
    async def test_renewal_alert_7_days(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800001)
        session.add(user)
        await session.flush()

        sub = make_subscription(
            user.id,
            service_name="Netflix",
            next_renewal_date=date.today() + timedelta(days=7),
        )
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)

        assert alerts == 1
        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args.kwargs["text"]
        assert "Renewal Alert" in msg
        assert "Netflix" in msg
        assert "7 days" in msg

    @pytest.mark.asyncio
    async def test_skip_non_threshold_day(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800002)
        session.add(user)
        await session.flush()

        sub = make_subscription(
            user.id,
            next_renewal_date=date.today() + timedelta(days=5),
        )
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)

        assert alerts == 0
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_price_hike_alert(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800003)
        session.add(user)
        await session.flush()

        sub = make_subscription(
            user.id,
            service_name="Netflix",
            amount=Decimal("64.00"),
            last_price=Decimal("54.00"),
            price_change_detected_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)

        assert alerts == 1
        msg = bot.send_message.call_args.kwargs["text"]
        assert "Price Change Alert" in msg
        assert "increased" in msg

    @pytest.mark.asyncio
    async def test_stale_price_change_skipped(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800004)
        session.add(user)
        await session.flush()

        sub = make_subscription(
            user.id,
            amount=Decimal("64.00"),
            last_price=Decimal("54.00"),
            price_change_detected_at=datetime.now(timezone.utc) - timedelta(hours=30),
        )
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)
        assert alerts == 0

    @pytest.mark.asyncio
    async def test_inactive_user_skipped(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800005, is_active=False)
        session.add(user)
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)
        assert alerts == 0
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_failure_logged(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800006)
        session.add(user)
        await session.flush()

        sub = make_subscription(
            user.id,
            next_renewal_date=date.today() + timedelta(days=3),
        )
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        bot.send_message.side_effect = Exception("Telegram API error")
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        # Should not raise, just log
        alerts = await svc.check_and_send_for_user(user.id)
        assert alerts == 0

    @pytest.mark.asyncio
    async def test_no_duplicate_alert_same_day(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800007)
        session.add(user)
        await session.flush()

        sub = make_subscription(
            user.id,
            next_renewal_date=date.today() + timedelta(days=7),
            last_renewal_alert_sent_at=date.today(),
        )
        session.add(sub)
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)
        assert alerts == 0
        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_redundant_service_note(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=800008)
        session.add(user)
        await session.flush()

        sub1 = make_subscription(
            user.id,
            service_name="Netflix",
            category="streaming",
            next_renewal_date=date.today() + timedelta(days=7),
        )
        sub2 = make_subscription(
            user.id,
            service_name="Disney+",
            category="streaming",
            amount=Decimal("39.90"),
        )
        session.add_all([sub1, sub2])
        await session.flush()

        bot = AsyncMock()
        settings = _make_settings()
        svc = AlertService(session, bot, settings)

        alerts = await svc.check_and_send_for_user(user.id)
        assert alerts == 1
        msg = bot.send_message.call_args.kwargs["text"]
        assert "Disney+" in msg
        assert "same category" in msg
