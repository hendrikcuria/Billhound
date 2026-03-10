from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.config.constants import DEFAULT_TIMEZONE
from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.db.models.cancellation_log import CancellationLog
    from src.db.models.oauth_token import OAuthToken
    from src.db.models.password_pattern import PasswordPattern
    from src.db.models.service_credential import ServiceCredential
    from src.db.models.subscription import Subscription


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    telegram_username: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(String(50), default=DEFAULT_TIMEZONE)

    # Relationships
    subscriptions: Mapped[list[Subscription]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    oauth_tokens: Mapped[list[OAuthToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_patterns: Mapped[list[PasswordPattern]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    cancellation_logs: Mapped[list[CancellationLog]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    service_credentials: Mapped[list[ServiceCredential]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
