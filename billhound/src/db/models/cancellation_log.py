from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.constants import CancellationStatus
from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.db.models.user import User


class CancellationLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cancellation_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CancellationStatus] = mapped_column(
        Enum(CancellationStatus, name="cancellation_status_enum",
             values_callable=lambda e: [m.value for m in e]),
        default=CancellationStatus.INITIATED,
    )
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    confirmed_saving_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    confirmed_saving_currency: Mapped[str | None] = mapped_column(String(3))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped[User] = relationship(back_populates="cancellation_logs")
