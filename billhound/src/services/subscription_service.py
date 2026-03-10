"""
Core business logic: create/update subscriptions from extracted data.
Handles deduplication, price hike detection, and confidence gating.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.constants import BillingCycle, SubscriptionStatus
from src.db.models.subscription import Subscription
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.email_ingestion.types import ExtractedSubscription
from src.services.merchant_db import lookup_category
from src.trust.audit import AuditWriter

logger = structlog.get_logger()

BILLING_CYCLE_MAP: dict[str, BillingCycle] = {
    "weekly": BillingCycle.WEEKLY,
    "monthly": BillingCycle.MONTHLY,
    "quarterly": BillingCycle.QUARTERLY,
    "semi_annual": BillingCycle.SEMI_ANNUAL,
    "annual": BillingCycle.ANNUAL,
}


class SubscriptionService:
    def __init__(
        self,
        session: AsyncSession,
        sub_repo: SubscriptionRepository,
        audit: AuditWriter,
        confidence_threshold: float = 0.70,
    ) -> None:
        self._session = session
        self._repo = sub_repo
        self._audit = audit
        self._threshold = confidence_threshold

    async def upsert_from_extraction(
        self,
        user_id: uuid.UUID,
        extractions: list[ExtractedSubscription],
    ) -> tuple[list[Subscription], int]:
        """
        Process extracted subscriptions: dedup, price hike detect, persist.
        Returns (subscriptions, price_changes_detected).

        Dedup is tracked both against existing DB rows *and* within the
        current batch, so multiple receipts for the same service in a
        single backfill pass collapse into one subscription.
        """
        existing = await self._repo.get_active_by_user(user_id)
        existing_map = {self._normalize(s.service_name): s for s in existing}

        results: list[Subscription] = []
        price_changes = 0

        for ext in extractions:
            key = self._normalize(ext.service_name)
            if key in existing_map:
                sub, changed = await self._update_existing(
                    existing_map[key], ext, user_id
                )
                if changed:
                    price_changes += 1
            else:
                sub = await self._create_new(user_id, ext)
                # Track within-batch dedup so subsequent extractions
                # for the same service update rather than create again
                existing_map[key] = sub
            results.append(sub)

        return results, price_changes

    async def _update_existing(
        self,
        sub: Subscription,
        ext: ExtractedSubscription,
        user_id: uuid.UUID,
    ) -> tuple[Subscription, bool]:
        """Update existing subscription. Returns (sub, price_changed)."""
        price_changed = False
        updates: dict = {}

        # Price hike detection
        if ext.amount and ext.amount != sub.amount:
            updates["last_price"] = sub.amount
            updates["amount"] = ext.amount
            updates["price_change_detected_at"] = datetime.now(timezone.utc)
            price_changed = True

            await self._audit.log(
                action="price_change_detected",
                user_id=user_id,
                entity_type="subscription",
                entity_id=str(sub.id),
                details={
                    "service": sub.service_name,
                    "old_price": str(sub.amount),
                    "new_price": str(ext.amount),
                },
            )
            logger.info(
                "subscription.price_change",
                service=sub.service_name,
                old=str(sub.amount),
                new=str(ext.amount),
            )

        # Update renewal date — only if newer than existing (temporal ordering)
        if ext.next_renewal_date and (
            not sub.next_renewal_date
            or ext.next_renewal_date > sub.next_renewal_date
        ):
            updates["next_renewal_date"] = ext.next_renewal_date

        if updates:
            updated = await self._repo.update(sub, **updates)
            return updated, price_changed

        return sub, False

    async def _create_new(
        self,
        user_id: uuid.UUID,
        ext: ExtractedSubscription,
    ) -> Subscription:
        """Create new subscription with confidence gating."""
        # Determine status
        if ext.confidence_score < self._threshold:
            status = SubscriptionStatus.PENDING_CONFIRMATION
        elif ext.trial_end_date:
            status = SubscriptionStatus.TRIAL
        else:
            status = SubscriptionStatus.ACTIVE

        # Category: merchant_db first, then LLM's suggestion
        category = lookup_category(ext.service_name) or ext.category or "other"

        billing_cycle = BILLING_CYCLE_MAP.get(
            ext.billing_cycle, BillingCycle.UNKNOWN
        )

        sub = await self._repo.create(
            user_id=user_id,
            service_name=ext.service_name,
            category=category,
            amount=ext.amount,
            currency=ext.currency,
            billing_cycle=billing_cycle,
            next_renewal_date=ext.next_renewal_date,
            trial_end_date=ext.trial_end_date,
            status=status,
            confidence_score=Decimal(str(ext.confidence_score)),
            source_email_subject=ext.source_email_subject,
            cancellation_url=ext.cancellation_url,
            is_manually_added=False,
        )

        await self._audit.log(
            action="subscription_detected",
            user_id=user_id,
            entity_type="subscription",
            entity_id=str(sub.id),
            details={
                "service": ext.service_name,
                "amount": str(ext.amount),
                "confidence": ext.confidence_score,
                "status": status.value,
            },
        )

        return sub

    @staticmethod
    def _normalize(name: str) -> str:
        return name.lower().strip()
