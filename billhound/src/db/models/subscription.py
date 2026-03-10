from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.constants import (
    DEFAULT_CURRENCY,
    BillingCycle,
    SubscriptionStatus,
)
from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.db.models.user import User


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default=DEFAULT_CURRENCY)
    billing_cycle: Mapped[BillingCycle] = mapped_column(
        Enum(BillingCycle, name="billing_cycle_enum",
             values_callable=lambda e: [m.value for m in e]),
        default=BillingCycle.MONTHLY,
    )
    next_renewal_date: Mapped[date | None] = mapped_column(Date)
    trial_end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum",
             values_callable=lambda e: [m.value for m in e]),
        default=SubscriptionStatus.ACTIVE,
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), default=Decimal("1.00")
    )
    source_email_subject: Mapped[str | None] = mapped_column(Text)
    is_manually_added: Mapped[bool] = mapped_column(Boolean, default=False)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_change_detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancellation_url: Mapped[str | None] = mapped_column(Text)
    last_renewal_alert_sent_at: Mapped[date | None] = mapped_column(Date)

    # Relationships
    user: Mapped[User] = relationship(back_populates="subscriptions")
