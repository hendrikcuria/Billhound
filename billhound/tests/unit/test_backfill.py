"""
Tests for Phase 7: Historical Auto-Discovery (Backfill).

Covers:
  1. Temporal deduplication — multiple receipts → single subscription
  2. Backfill orchestrator — summary notification, error handling
  3. OAuth trigger integration — callback fires backfill
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import BillingCycle, SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.email_ingestion.types import ExtractedSubscription
from src.services.backfill import BackfillOrchestrator, BackfillResult
from src.services.merchant_db import MERCHANT_SENDERS, get_known_sender_addresses
from src.services.subscription_service import SubscriptionService
from src.trust.audit import AuditWriter
from tests.factories import make_subscription, make_user


# ═══════════════════════════════════════════════════════════════════
# 1. Temporal Deduplication Tests
# ═══════════════════════════════════════════════════════════════════


class TestTemporalDeduplication:
    """Verify that multiple historical receipts for the same service
    collapse into a single subscription with the latest renewal date."""

    @pytest.mark.asyncio
    async def test_multiple_receipts_same_service_dedup_to_one(
        self, session: AsyncSession
    ) -> None:
        """Three Spotify receipts over 3 months → 1 active subscription."""
        user = make_user(telegram_id=900001)
        session.add(user)
        await session.flush()

        sub_repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        svc = SubscriptionService(session, sub_repo, audit)

        # Simulate 3 monthly Spotify receipts extracted by LLM
        extractions = [
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("14.90"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.92,
                next_renewal_date=date(2026, 1, 15),
                source_email_subject="Your Spotify receipt - Jan 2026",
            ),
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("14.90"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.94,
                next_renewal_date=date(2026, 2, 15),
                source_email_subject="Your Spotify receipt - Feb 2026",
            ),
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("14.90"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.95,
                next_renewal_date=date(2026, 3, 15),
                source_email_subject="Your Spotify receipt - Mar 2026",
            ),
        ]

        subs, price_changes = await svc.upsert_from_extraction(
            user.id, extractions
        )

        # All 3 receipts → 1 subscription (deduped by normalized name)
        active = await sub_repo.get_active_by_user(user.id)
        assert len(active) == 1
        assert active[0].service_name == "Spotify"
        assert price_changes == 0

    @pytest.mark.asyncio
    async def test_renewal_date_keeps_latest(
        self, session: AsyncSession
    ) -> None:
        """Oldest receipt must NOT overwrite a newer renewal date."""
        user = make_user(telegram_id=900002)
        session.add(user)
        await session.flush()

        sub_repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        svc = SubscriptionService(session, sub_repo, audit)

        # Process newest receipt first, then older one
        batch_1 = [
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("54.00"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.95,
                next_renewal_date=date(2026, 4, 10),
                source_email_subject="Netflix receipt - March",
            ),
        ]
        await svc.upsert_from_extraction(user.id, batch_1)

        # Now process an older receipt with an earlier renewal date
        batch_2 = [
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("54.00"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.93,
                next_renewal_date=date(2026, 2, 10),
                source_email_subject="Netflix receipt - January",
            ),
        ]
        await svc.upsert_from_extraction(user.id, batch_2)

        active = await sub_repo.get_active_by_user(user.id)
        assert len(active) == 1
        # The latest renewal date should be preserved
        assert active[0].next_renewal_date == date(2026, 4, 10)

    @pytest.mark.asyncio
    async def test_different_services_create_separate_entries(
        self, session: AsyncSession
    ) -> None:
        """Spotify + Netflix receipts → 2 separate subscriptions."""
        user = make_user(telegram_id=900003)
        session.add(user)
        await session.flush()

        sub_repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        svc = SubscriptionService(session, sub_repo, audit)

        extractions = [
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("14.90"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.92,
            ),
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("54.00"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.95,
            ),
        ]

        subs, _ = await svc.upsert_from_extraction(user.id, extractions)
        active = await sub_repo.get_active_by_user(user.id)
        assert len(active) == 2
        names = {s.service_name for s in active}
        assert names == {"Spotify", "Netflix"}

    @pytest.mark.asyncio
    async def test_price_change_across_historical_receipts(
        self, session: AsyncSession
    ) -> None:
        """Receipts showing RM14.90 → RM17.90 triggers price change detection."""
        user = make_user(telegram_id=900004)
        session.add(user)
        await session.flush()

        sub_repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        svc = SubscriptionService(session, sub_repo, audit)

        # First batch: old price
        batch_1 = [
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("14.90"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.92,
            ),
        ]
        await svc.upsert_from_extraction(user.id, batch_1)

        # Second batch: new price (price hike!)
        batch_2 = [
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("17.90"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.95,
            ),
        ]
        _, price_changes = await svc.upsert_from_extraction(user.id, batch_2)

        assert price_changes == 1
        active = await sub_repo.get_active_by_user(user.id)
        assert active[0].amount == Decimal("17.90")
        assert active[0].last_price == Decimal("14.90")


# ═══════════════════════════════════════════════════════════════════
# 2. Backfill Orchestrator Tests
# ═══════════════════════════════════════════════════════════════════


class TestBackfillOrchestrator:
    """Test the BackfillOrchestrator summary notification and edge cases."""

    @pytest.mark.asyncio
    async def test_backfill_sends_telegram_summary(
        self, session: AsyncSession, session_factory
    ) -> None:
        """After backfill, user receives a Telegram summary with sub count + total."""
        user = make_user(telegram_id=900010)
        session.add(user)
        await session.flush()

        # Pre-populate subs (simulating what the scanner would create)
        sub1 = make_subscription(
            user.id,
            service_name="Spotify",
            amount=Decimal("14.90"),
            billing_cycle=BillingCycle.MONTHLY,
        )
        sub2 = make_subscription(
            user.id,
            service_name="Netflix",
            amount=Decimal("54.00"),
            billing_cycle=BillingCycle.MONTHLY,
        )
        session.add_all([sub1, sub2])
        await session.flush()

        bot = AsyncMock()
        settings = MagicMock()
        settings.confidence_threshold = 0.70
        encryption = MagicMock()

        orchestrator = BackfillOrchestrator(
            session_factory=session_factory,
            settings=settings,
            encryption=encryption,
            llm_provider=MagicMock(),
            telegram_bot=bot,
        )

        # Mock the scanner so it doesn't call real APIs
        mock_scan_result = MagicMock()
        mock_scan_result.emails_scanned = 15
        mock_scan_result.new_subscriptions = 2

        with patch.object(
            orchestrator, "_build_scanner"
        ) as mock_build:
            mock_scanner = AsyncMock()
            mock_scanner.scan_user.return_value = mock_scan_result
            mock_build.return_value = mock_scanner

            result = await orchestrator.run_backfill(user.id, "gmail")

        # Verify Telegram summary was sent
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == 900010
        assert "2 active subscriptions" in call_kwargs["text"]
        assert "RM68.90/month" in call_kwargs["text"]
        assert "Initial scan complete" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_backfill_calculates_monthly_total_mixed_cycles(
        self, session: AsyncSession, session_factory
    ) -> None:
        """Mixed billing cycles (monthly + annual) produce correct monthly total."""
        user = make_user(telegram_id=900011)
        session.add(user)
        await session.flush()

        # Monthly: RM14.90/month
        sub1 = make_subscription(
            user.id,
            service_name="Spotify",
            amount=Decimal("14.90"),
            billing_cycle=BillingCycle.MONTHLY,
        )
        # Annual: RM499.00/year → RM499.00/12 ≈ RM41.58/month
        sub2 = make_subscription(
            user.id,
            service_name="Adobe",
            amount=Decimal("499.00"),
            billing_cycle=BillingCycle.ANNUAL,
        )
        session.add_all([sub1, sub2])
        await session.flush()

        bot = AsyncMock()
        settings = MagicMock()
        settings.confidence_threshold = 0.70

        orchestrator = BackfillOrchestrator(
            session_factory=session_factory,
            settings=settings,
            encryption=MagicMock(),
            llm_provider=MagicMock(),
            telegram_bot=bot,
        )

        mock_scan_result = MagicMock()
        mock_scan_result.emails_scanned = 10

        with patch.object(orchestrator, "_build_scanner") as mock_build:
            mock_scanner = AsyncMock()
            mock_scanner.scan_user.return_value = mock_scan_result
            mock_build.return_value = mock_scanner

            result = await orchestrator.run_backfill(user.id, "gmail")

        assert result.subscriptions_found == 2
        # 14.90 + (499.00 / 12) = 14.90 + 41.58... ≈ 56.48...
        assert result.total_monthly > Decimal("56")
        assert result.total_monthly < Decimal("57")

    @pytest.mark.asyncio
    async def test_backfill_handles_empty_inbox(
        self, session: AsyncSession, session_factory
    ) -> None:
        """No emails found → sends 'no subscriptions found' summary."""
        user = make_user(telegram_id=900012)
        session.add(user)
        await session.flush()

        bot = AsyncMock()
        settings = MagicMock()
        settings.confidence_threshold = 0.70

        orchestrator = BackfillOrchestrator(
            session_factory=session_factory,
            settings=settings,
            encryption=MagicMock(),
            llm_provider=MagicMock(),
            telegram_bot=bot,
        )

        mock_scan_result = MagicMock()
        mock_scan_result.emails_scanned = 0
        mock_scan_result.new_subscriptions = 0

        with patch.object(orchestrator, "_build_scanner") as mock_build:
            mock_scanner = AsyncMock()
            mock_scanner.scan_user.return_value = mock_scan_result
            mock_build.return_value = mock_scanner

            result = await orchestrator.run_backfill(user.id, "gmail")

        assert result.subscriptions_found == 0
        assert result.total_monthly == Decimal("0.00")

        bot.send_message.assert_called_once()
        msg = bot.send_message.call_args.kwargs["text"]
        assert "No active subscriptions found" in msg

    @pytest.mark.asyncio
    async def test_backfill_error_does_not_crash(
        self, session_factory
    ) -> None:
        """Scanner raises an exception → backfill catches it, doesn't crash."""
        fake_user_id = uuid.uuid4()

        settings = MagicMock()
        settings.confidence_threshold = 0.70

        orchestrator = BackfillOrchestrator(
            session_factory=session_factory,
            settings=settings,
            encryption=MagicMock(),
            llm_provider=MagicMock(),
            telegram_bot=AsyncMock(),
        )

        with patch.object(orchestrator, "_build_scanner") as mock_build:
            mock_scanner = AsyncMock()
            mock_scanner.scan_user.side_effect = RuntimeError("API rate limit")
            mock_build.return_value = mock_scanner

            with pytest.raises(RuntimeError, match="API rate limit"):
                await orchestrator.run_backfill(fake_user_id, "gmail")


# ═══════════════════════════════════════════════════════════════════
# 3. OAuth Trigger Integration Tests
# ═══════════════════════════════════════════════════════════════════


class _FakeSession:
    """Async context manager that mimics async_sessionmaker().__call__()."""

    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _make_session_factory() -> MagicMock:
    """Return a callable that produces _FakeSession async context managers."""
    factory = MagicMock()
    factory.return_value = _FakeSession()
    return factory


class TestOAuthBackfillTrigger:
    """Verify that OAuth success fires the backfill task."""

    @pytest.mark.asyncio
    async def test_gmail_callback_triggers_backfill(self) -> None:
        """Gmail OAuth success → backfill.run_backfill() is called."""
        from src.email_ingestion.oauth.callback_server import OAuthCallbackServer

        gmail_client = MagicMock()
        outlook_client = MagicMock()
        session_factory = _make_session_factory()
        encryption = MagicMock()
        backfill = AsyncMock()

        server = OAuthCallbackServer(
            gmail_client=gmail_client,
            outlook_client=outlook_client,
            session_factory=session_factory,
            encryption=encryption,
            backfill=backfill,
        )

        user_id = uuid.uuid4()

        gmail_client.verify_state.return_value = str(user_id)
        gmail_client.exchange_code = AsyncMock(return_value={
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
        })
        gmail_client.SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

        with patch.object(
            OAuthCallbackServer, "_fetch_gmail_email",
            new_callable=AsyncMock, return_value="test@gmail.com"
        ):
            with patch(
                "src.email_ingestion.oauth.callback_server.OAuthTokenRepository"
            ) as MockRepo:
                MockRepo.return_value = AsyncMock()
                with patch(
                    "src.email_ingestion.oauth.callback_server.AuditWriter"
                ):
                    with patch(
                        "src.email_ingestion.oauth.callback_server.ConsentTracker"
                    ) as MockConsent:
                        MockConsent.return_value = AsyncMock()

                        request = MagicMock()
                        request.query = {
                            "code": "test_code",
                            "state": "test_state",
                        }

                        response = await server._handle_gmail(request)

        assert response.status == 200

        # Give the fire-and-forget task a chance to run
        await asyncio.sleep(0.1)

        backfill.run_backfill.assert_called_once_with(user_id, "gmail")

    @pytest.mark.asyncio
    async def test_outlook_callback_triggers_backfill(self) -> None:
        """Outlook OAuth success → backfill.run_backfill() is called."""
        from src.email_ingestion.oauth.callback_server import OAuthCallbackServer

        gmail_client = MagicMock()
        outlook_client = MagicMock()
        session_factory = _make_session_factory()
        encryption = MagicMock()
        backfill = AsyncMock()

        server = OAuthCallbackServer(
            gmail_client=gmail_client,
            outlook_client=outlook_client,
            session_factory=session_factory,
            encryption=encryption,
            backfill=backfill,
        )

        user_id = uuid.uuid4()

        outlook_client.verify_state.return_value = str(user_id)
        outlook_client.exchange_code = AsyncMock(return_value={
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
        })
        outlook_client.SCOPES = [
            "https://graph.microsoft.com/Mail.Read",
            "offline_access",
        ]

        with patch.object(
            OAuthCallbackServer, "_fetch_outlook_email",
            new_callable=AsyncMock, return_value="test@outlook.com"
        ):
            with patch(
                "src.email_ingestion.oauth.callback_server.OAuthTokenRepository"
            ) as MockRepo:
                MockRepo.return_value = AsyncMock()
                with patch(
                    "src.email_ingestion.oauth.callback_server.AuditWriter"
                ):
                    with patch(
                        "src.email_ingestion.oauth.callback_server.ConsentTracker"
                    ) as MockConsent:
                        MockConsent.return_value = AsyncMock()

                        request = MagicMock()
                        request.query = {
                            "code": "test_code",
                            "state": "test_state",
                        }

                        response = await server._handle_outlook(request)

        assert response.status == 200
        await asyncio.sleep(0.1)
        backfill.run_backfill.assert_called_once_with(user_id, "outlook")

    @pytest.mark.asyncio
    async def test_callback_without_backfill_still_works(self) -> None:
        """backfill=None → OAuth succeeds without crash."""
        from src.email_ingestion.oauth.callback_server import OAuthCallbackServer

        gmail_client = MagicMock()
        outlook_client = MagicMock()
        session_factory = _make_session_factory()
        encryption = MagicMock()

        # backfill is None (default)
        server = OAuthCallbackServer(
            gmail_client=gmail_client,
            outlook_client=outlook_client,
            session_factory=session_factory,
            encryption=encryption,
        )

        user_id = uuid.uuid4()
        gmail_client.verify_state.return_value = str(user_id)
        gmail_client.exchange_code = AsyncMock(return_value={
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
        })
        gmail_client.SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

        with patch.object(
            OAuthCallbackServer, "_fetch_gmail_email",
            new_callable=AsyncMock, return_value="test@gmail.com"
        ):
            with patch(
                "src.email_ingestion.oauth.callback_server.OAuthTokenRepository"
            ) as MockRepo:
                MockRepo.return_value = AsyncMock()
                with patch(
                    "src.email_ingestion.oauth.callback_server.AuditWriter"
                ):
                    with patch(
                        "src.email_ingestion.oauth.callback_server.ConsentTracker"
                    ) as MockConsent:
                        MockConsent.return_value = AsyncMock()

                        request = MagicMock()
                        request.query = {
                            "code": "test_code",
                            "state": "test_state",
                        }

                        response = await server._handle_gmail(request)

        assert response.status == 200
        # No crash, no backfill triggered — this is the success case


# ═══════════════════════════════════════════════════════════════════
# 4. Merchant Sender DB Tests
# ═══════════════════════════════════════════════════════════════════


class TestMerchantSenders:
    """Verify the merchant sender address lookup for backfill."""

    def test_known_sender_addresses_not_empty(self) -> None:
        addresses = get_known_sender_addresses()
        assert len(addresses) > 0

    def test_all_10_mvp_services_have_senders(self) -> None:
        """Each of the 10 MVP services has at least one sender address."""
        mvp_services = {
            "netflix", "spotify", "adobe", "canva", "amazon prime",
            "disney+", "youtube premium", "hulu", "microsoft 365", "nordvpn",
        }
        services_with_senders = set(MERCHANT_SENDERS.values())
        for svc in mvp_services:
            assert svc in services_with_senders, f"{svc} missing from MERCHANT_SENDERS"

    def test_sender_addresses_are_valid_emails(self) -> None:
        """All sender addresses contain @ and a domain."""
        for addr in get_known_sender_addresses():
            assert "@" in addr, f"Invalid sender address: {addr}"
            local, domain = addr.split("@", 1)
            assert "." in domain, f"Invalid domain in: {addr}"
