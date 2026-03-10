"""Encrypted service credentials for browser-based login automation."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from src.db.models.user import User


class ServiceCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "service_name", name="uq_user_service"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    username_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    auth_method: Mapped[str] = mapped_column(
        String(20), default="credential", nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="service_credentials")
