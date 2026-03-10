"""Tests for SubscriptionService — dedup, price hike detection, confidence gating."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import SubscriptionStatus
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.email_ingestion.types import ExtractedSubscription
from src.services.subscription_service import SubscriptionService
from src.trust.audit import AuditWriter
from tests.factories import make_subscription, make_user


class TestSubscriptionService:
    @pytest.mark.asyncio
    async def test_create_new_subscription(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=700001)
        session.add(user)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit)

        extractions = [
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("54.00"),
                currency="MYR",
                billing_cycle="monthly",
                confidence_score=0.95,
                source_email_subject="Your Netflix receipt",
            )
        ]

        subs, price_changes = await service.upsert_from_extraction(
            user.id, extractions
        )
        assert len(subs) == 1
        assert subs[0].service_name == "Netflix"
        assert subs[0].amount == Decimal("54.00")
        assert subs[0].status == SubscriptionStatus.ACTIVE
        assert price_changes == 0

    @pytest.mark.asyncio
    async def test_low_confidence_pending(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=700002)
        session.add(user)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit, confidence_threshold=0.70)

        extractions = [
            ExtractedSubscription(
                service_name="Unknown Service",
                amount=Decimal("29.90"),
                confidence_score=0.45,
            )
        ]

        subs, _ = await service.upsert_from_extraction(user.id, extractions)
        assert subs[0].status == SubscriptionStatus.PENDING_CONFIRMATION

    @pytest.mark.asyncio
    async def test_trial_status(self, session: AsyncSession) -> None:
        from datetime import date

        user = make_user(telegram_id=700003)
        session.add(user)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit)

        extractions = [
            ExtractedSubscription(
                service_name="Disney+",
                amount=Decimal("39.90"),
                confidence_score=0.90,
                trial_end_date=date(2026, 4, 1),
            )
        ]

        subs, _ = await service.upsert_from_extraction(user.id, extractions)
        assert subs[0].status == SubscriptionStatus.TRIAL

    @pytest.mark.asyncio
    async def test_dedup_updates_existing(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=700004)
        session.add(user)
        await session.flush()

        # Pre-existing subscription
        existing = make_subscription(
            user.id, service_name="Netflix", amount=Decimal("54.00")
        )
        session.add(existing)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit)

        # Same service, same price — should not create duplicate
        extractions = [
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("54.00"),
                confidence_score=0.95,
            )
        ]

        subs, price_changes = await service.upsert_from_extraction(
            user.id, extractions
        )
        assert len(subs) == 1
        assert subs[0].id == existing.id  # Same record updated, not new
        assert price_changes == 0

    @pytest.mark.asyncio
    async def test_price_hike_detection(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=700005)
        session.add(user)
        await session.flush()

        existing = make_subscription(
            user.id, service_name="Netflix", amount=Decimal("54.00")
        )
        session.add(existing)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit)

        # Price increased
        extractions = [
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("64.00"),
                confidence_score=0.95,
            )
        ]

        subs, price_changes = await service.upsert_from_extraction(
            user.id, extractions
        )
        assert price_changes == 1
        assert subs[0].amount == Decimal("64.00")
        assert subs[0].last_price == Decimal("54.00")
        assert subs[0].price_change_detected_at is not None

    @pytest.mark.asyncio
    async def test_category_from_merchant_db(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=700006)
        session.add(user)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit)

        extractions = [
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("15.90"),
                confidence_score=0.90,
                category=None,  # LLM didn't provide
            )
        ]

        subs, _ = await service.upsert_from_extraction(user.id, extractions)
        assert subs[0].category == "music"  # From merchant_db

    @pytest.mark.asyncio
    async def test_multiple_extractions(self, session: AsyncSession) -> None:
        user = make_user(telegram_id=700007)
        session.add(user)
        await session.flush()

        repo = SubscriptionRepository(session)
        audit = AuditWriter(session)
        service = SubscriptionService(session, repo, audit)

        extractions = [
            ExtractedSubscription(
                service_name="Netflix",
                amount=Decimal("54.00"),
                confidence_score=0.95,
            ),
            ExtractedSubscription(
                service_name="Spotify",
                amount=Decimal("15.90"),
                confidence_score=0.90,
            ),
        ]

        subs, _ = await service.upsert_from_extraction(user.id, extractions)
        assert len(subs) == 2
